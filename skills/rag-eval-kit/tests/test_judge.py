import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from rag_eval_kit.budget import BudgetLedger
from rag_eval_kit.config import JudgeConfig
from rag_eval_kit.judge import BudgetedOpenAIJudge, JudgeError


class Answer(BaseModel):
    answer: str


class FakeClient:
    def __init__(self, response=None, error=None):
        self.chat = SimpleNamespace(completions=self)
        self.response = response
        self.error = error
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.response

    def close(self):
        pass


def config(**kwargs):
    return JudgeConfig(
        model="fixture-model",
        price={
            "input_usd_per_million": "1",
            "output_usd_per_million": "2",
            "source_url": "https://example.test/rates",
            "checked_on": date.today(),
        },
        **kwargs,
    )


def response(content='{"answer":"ready"}', usage=True, finish="stop"):
    return SimpleNamespace(
        model="fixture-response-model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5) if usage else None,
        choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))],
    )


def test_schema_generation_and_usage_are_verified_before_return():
    ledger = BudgetLedger(Decimal(1))
    client = FakeClient(response())
    judge = BudgetedOpenAIJudge(config(), ledger, "unused-fixture", client=client)
    assert judge.generate("Say ready", Answer).answer == "ready"
    assert ledger.snapshot()["components"]["judge"]["input_tokens"] == 10
    assert ledger.calls[0].response_model == "fixture-response-model"
    assert ledger.calls[0].finish_reason == "stop"
    assert client.requests[0]["response_format"] == {"type": "json_object"}
    assert client.requests[0]["model"] == "fixture-model"
    assert client.requests[0]["max_completion_tokens"] == 1024


def test_async_generation_uses_same_accounted_path():
    ledger = BudgetLedger(Decimal(1))
    client = FakeClient(response())
    judge = BudgetedOpenAIJudge(config(), ledger, "unused-fixture", client=client)
    assert asyncio.run(judge.a_generate("Say ready", Answer)).answer == "ready"
    assert len(ledger.calls) == 1


def test_budget_rejection_happens_before_network():
    client = FakeClient(response())
    judge = BudgetedOpenAIJudge(config(), BudgetLedger(Decimal("0.000001")), "unused", client)
    with pytest.raises(RuntimeError):
        judge.generate("Say ready", Answer)
    assert client.requests == []


def test_unbounded_prompt_is_rejected_without_a_call():
    client = FakeClient(response())
    judge = BudgetedOpenAIJudge(
        config(input_token_cap=4096), BudgetLedger(Decimal(1)), "unused", client
    )
    with pytest.raises(JudgeError, match="input-token bound"):
        judge.generate("x" * 4096, Answer)
    assert client.requests == []


@pytest.mark.parametrize(
    "reply", [response(usage=False), response(finish="length"), response("bad json")]
)
def test_missing_usage_truncation_and_bad_json_fail_closed(reply):
    ledger = BudgetLedger(Decimal(1))
    client = FakeClient(reply)
    judge = BudgetedOpenAIJudge(config(), ledger, "unused", client)
    with pytest.raises(JudgeError):
        judge.generate("Say ready", Answer)
    assert len(client.requests) == 1
    if reply.usage is None:
        assert ledger.blocked and ledger.calls[0].status == "unverified"
    else:
        assert ledger.calls[0].status == "verified"


def test_provider_error_text_is_not_exposed_and_unknown_charge_is_reserved():
    ledger = BudgetLedger(Decimal(1))
    client = FakeClient(error=RuntimeError("sensitive-provider-echo"))
    judge = BudgetedOpenAIJudge(config(), ledger, "unused", client)
    with pytest.raises(JudgeError) as result:
        judge.generate("Say ready", Answer)
    assert "sensitive-provider-echo" not in str(result.value)
    assert ledger.calls[0].status == "unverified"
    assert ledger.committed > 0
    assert len(client.requests) == 1
