"""Canned schema responses for compatibility only: never an answer-quality judge."""

from typing import Any

from pydantic import BaseModel

from rag_eval_kit.privacy import configure_local_runtime

configure_local_runtime()

from deepeval.models import DeepEvalBaseLLM  # noqa: E402


class OfflineSchemaJudge(DeepEvalBaseLLM):
    def __init__(self) -> None:
        self.calls: list[str] = []
        super().__init__(model="offline-schema-fixture")

    def load_model(self) -> "OfflineSchemaJudge":
        return self

    def get_model_name(self) -> str:
        return "offline-schema-fixture-NOT-A-QUALITY-JUDGE"

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        self.calls.append(schema.__name__ if schema else "text")
        if schema is None:
            return "Fixture response: unused items may be returned within 30 days."
        fields = set(schema.model_fields)
        payload: dict[str, Any]
        if "verdicts" in fields:
            payload = {
                "verdicts": [
                    {
                        "verdict": "yes",
                        "reason": "Canned fixture, not a quality judgment.",
                        "statement": "Fixture statement.",
                    }
                ]
            }
        elif "truths" in fields:
            payload = {"truths": ["Fixture fact."]}
        elif "claims" in fields:
            payload = {"claims": ["Fixture claim."]}
        elif "statements" in fields:
            payload = {"statements": ["Fixture statement."]}
        elif "reason" in fields:
            payload = {"reason": "Canned schema compatibility fixture; not evaluation evidence."}
        elif "data" in fields:
            payload = {"data": [{"input": "What is the return window?"}]}
        elif {"score", "feedback"} <= fields:
            payload = {"score": 1.0, "feedback": "Fixture only; human review remains required."}
        elif "rewritten_input" in fields:
            payload = {"rewritten_input": "What is the return window?"}
        elif "response" in fields:
            payload = {"response": "Unused items may be returned within 30 days."}
        else:
            raise RuntimeError(f"Unsupported installed DeepEval schema: {schema.__name__}")
        return schema.model_validate(payload)

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        return self.generate(prompt, schema)
