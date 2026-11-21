from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest

from rag_eval_kit.budget import BudgetError, BudgetLedger
from rag_eval_kit.config import Price


def price():
    # Synthetic test rates, not provider pricing.
    return Price(
        input_usd_per_million=1,
        output_usd_per_million=2,
        source_url="https://example.test/pricing",
        checked_on=date.today(),
    )


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_budget_is_rejected(value):
    with pytest.raises(ValueError):
        BudgetLedger(Decimal(value))


def test_pending_reservations_prevent_overspend():
    ledger = BudgetLedger(Decimal("0.000004"))
    index = ledger.reserve("judge", "fixture", price(), 2, 1)
    assert index == 0
    with pytest.raises(BudgetError):
        ledger.reserve("judge", "fixture", price(), 1, 0)
    ledger.settle(index, price(), 1, 0)
    assert ledger.committed == Decimal("0.000001")
    ledger.reserve("judge", "fixture", price(), 1, 1)


def test_components_account_for_separate_input_and_output_tokens():
    ledger = BudgetLedger(Decimal(1))
    for component in ("judge", "builder_generation", "builder_embedding"):
        index = ledger.reserve(component, "fixture", price(), 10, 10)
        ledger.settle(index, price(), 4, 2)
    snapshot = ledger.snapshot()
    for component in snapshot["components"].values():
        assert component == {
            "status": "verified",
            "input_tokens": 4,
            "output_tokens": 2,
            "known_cost_usd": "0.000008",
            "committed_or_reserved_usd": "0.000008",
        }


def test_missing_usage_keeps_reservation_and_blocks_future_calls():
    ledger = BudgetLedger(Decimal(1))
    index = ledger.reserve("judge", "fixture", price(), 20, 10)
    with pytest.raises(BudgetError, match="Usage unavailable"):
        ledger.settle(index, price(), 20, None)
    assert ledger.calls[index].cost_usd is None
    assert ledger.committed == Decimal("0.00004")
    component = ledger.snapshot()["components"]["judge"]
    assert component["status"] == "unverified"
    assert component["input_tokens"] is None
    assert component["output_tokens"] is None
    assert component["known_cost_usd"] is None
    assert component["committed_or_reserved_usd"] == "0.00004"
    assert ledger.calls[index].input_tokens == 20
    assert ledger.calls[index].output_tokens is None
    with pytest.raises(BudgetError):
        ledger.reserve("judge", "fixture", price(), 1, 1)


def test_failed_request_never_becomes_free_and_cannot_be_retried():
    ledger = BudgetLedger(Decimal(1))
    index = ledger.reserve("judge", "fixture", price(), 10, 10)
    ledger.fail(index)
    assert ledger.committed == Decimal("0.00003")
    with pytest.raises(BudgetError):
        ledger.reserve("judge", "fixture", price(), 1, 1)


def test_actual_usage_overrun_blocks_subsequent_calls():
    ledger = BudgetLedger(Decimal(1))
    index = ledger.reserve("judge", "fixture", price(), 1, 1)
    with pytest.raises(BudgetError, match="exceeded reservation"):
        ledger.settle(index, price(), 10, 10)
    assert ledger.committed == Decimal("0.00003")
    assert ledger.blocked


def test_exact_budget_and_max_call_count_stop_new_work():
    ledger = BudgetLedger(Decimal(1), max_calls=1)
    index = ledger.reserve("judge", "fixture", price(), 1, 1)
    ledger.settle(index, price(), 0, 0)
    with pytest.raises(BudgetError):
        ledger.reserve("judge", "fixture", price(), 1, 1)
    with pytest.raises(BudgetError):
        ledger.settle(index, price(), 0, 0)


def test_concurrent_reservations_are_atomic():
    ledger = BudgetLedger(Decimal("0.000003"))

    def reserve(_):
        try:
            return ledger.reserve("judge", "fixture", price(), 1, 1)
        except BudgetError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(8)))
    assert sum(item is not None for item in results) == 1
    assert ledger.committed == ledger.limit


def test_reservation_callback_runs_before_paid_work():
    ledger = BudgetLedger(Decimal(1))
    snapshots = []
    ledger.on_change = lambda: snapshots.append(ledger.snapshot())
    ledger.reserve("judge", "fixture", price(), 1, 1)
    assert snapshots[0]["calls"][0]["status"] == "pending"
