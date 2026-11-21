"""DeepEval custom judge using one budgeted OpenAI request per generation."""

import asyncio
import json
from typing import Any

import httpx
from openai import OpenAI
from pydantic import BaseModel

from rag_eval_kit.budget import BudgetLedger
from rag_eval_kit.config import JudgeConfig
from rag_eval_kit.privacy import configure_local_runtime

configure_local_runtime()

from deepeval.models import DeepEvalBaseLLM  # noqa: E402


class JudgeError(RuntimeError):
    pass


class BudgetedOpenAIJudge(DeepEvalBaseLLM):
    def __init__(
        self,
        config: JudgeConfig,
        ledger: BudgetLedger,
        api_key: str,
        client: Any = None,
    ) -> None:
        self.config = config
        self.ledger = ledger
        self._client = client or OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=config.timeout_seconds,
            http_client=httpx.Client(trust_env=False, follow_redirects=False),
        )
        super().__init__(model=config.model)

    def load_model(self) -> Any:
        return self._client

    def get_model_name(self) -> str:
        return self.config.model

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        schema_json = json.dumps(schema.model_json_schema()) if schema else ""
        # UTF-8 bytes overbound ordinary byte-BPE tokens; reserve extra request/schema framing.
        bound = len(prompt.encode("utf-8")) + len(schema_json.encode("utf-8")) + 4096
        if bound > self.config.input_token_cap:
            raise JudgeError("Prompt exceeds the configured conservative input-token bound")
        instruction = (
            "Return only a JSON object matching this schema: " + schema_json if schema else ""
        )
        token = self.ledger.reserve(
            "judge",
            self.config.model,
            self.config.price,
            self.config.input_token_cap,
            self.config.max_output_tokens,
        )
        try:
            messages = [{"role": "user", "content": prompt}]
            if schema:
                messages.insert(0, {"role": "system", "content": instruction})
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "max_completion_tokens": self.config.max_output_tokens,
            }
            if schema:
                kwargs["response_format"] = {"type": "json_object"}
            completion = self._client.chat.completions.create(**kwargs)
            usage = completion.usage
            choice = completion.choices[0]
            self.ledger.settle(
                token,
                self.config.price,
                usage.prompt_tokens if usage else None,
                usage.completion_tokens if usage else None,
                response_model=completion.model,
                finish_reason=choice.finish_reason,
            )
            if choice.finish_reason != "stop" or not choice.message.content:
                raise JudgeError("Judge did not return a complete answer; inspect finish reason")
            return (
                schema.model_validate_json(choice.message.content)
                if schema
                else choice.message.content
            )
        except Exception as error:
            self.ledger.fail(token)
            # Provider error payloads can echo requests; never copy them into public reports.
            raise JudgeError(
                f"Judge call failed ({type(error).__name__}); no automatic retry"
            ) from None

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        return await asyncio.to_thread(self.generate, prompt, schema)

    def close(self) -> None:
        self._client.close()
