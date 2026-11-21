"""Conservative, per-run reservations with explicit unknown-usage handling."""

from collections.abc import Callable
from decimal import Decimal
from threading import RLock
from typing import Literal

from pydantic import BaseModel

from rag_eval_kit.config import Price

Component = Literal["judge", "builder_generation", "builder_embedding"]
COMPONENTS: tuple[Component, ...] = ("judge", "builder_generation", "builder_embedding")


class BudgetError(RuntimeError):
    pass


class CallRecord(BaseModel):
    component: Component
    model: str
    reserved_usd: Decimal
    status: Literal["pending", "verified", "unverified"] = "pending"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal | None = None
    response_model: str | None = None
    finish_reason: str | None = None


class BudgetLedger:
    def __init__(self, limit: Decimal, max_calls: int = 100) -> None:
        if not limit.is_finite() or limit <= 0 or max_calls < 1:
            raise ValueError("Budget must be finite and positive; max_calls must be positive")
        self.limit = limit
        self.max_calls = max_calls
        self.calls: list[CallRecord] = []
        self.blocked = False
        self._lock = RLock()
        self.on_change: Callable[[], None] = lambda: None

    @property
    def committed(self) -> Decimal:
        return (
            sum(
                (call.cost_usd if call.cost_usd is not None else call.reserved_usd)
                for call in self.calls
            )
            if self.calls
            else Decimal(0)
        )

    def reserve(
        self, component: Component, model: str, price: Price, input_tokens: int, output_tokens: int
    ) -> int:
        if component not in COMPONENTS or min(input_tokens, output_tokens) < 0:
            raise ValueError("Invalid component or negative token reservation")
        with self._lock:
            estimate = price.cost(input_tokens, output_tokens)
            if self.blocked or len(self.calls) >= self.max_calls:
                raise BudgetError("Run stopped: unresolved usage or maximum call count reached")
            if self.committed >= self.limit or self.committed + estimate > self.limit:
                raise BudgetError("Budget cannot cover this call and existing reservations")
            self.calls.append(CallRecord(component=component, model=model, reserved_usd=estimate))
            # Persist the pending reservation before any external request starts.
            self.on_change()
            return len(self.calls) - 1

    def settle(
        self,
        index: int,
        price: Price,
        input_tokens: int | None,
        output_tokens: int | None,
        response_model: str | None = None,
        finish_reason: str | None = None,
    ) -> None:
        with self._lock:
            call = self.calls[index]
            if call.status != "pending":
                raise BudgetError("Call was already settled")
            call.response_model = response_model
            call.finish_reason = finish_reason
            call.input_tokens = input_tokens
            call.output_tokens = output_tokens
            if input_tokens is None or output_tokens is None:
                call.status = "unverified"
                self.blocked = True
                self.on_change()
                raise BudgetError(
                    "Usage unavailable; reservation retained and further calls blocked"
                )
            if min(input_tokens, output_tokens) < 0:
                raise ValueError("Provider token counts cannot be negative")
            call.cost_usd = price.cost(input_tokens, output_tokens)
            call.status = "verified"
            overrun = call.cost_usd > call.reserved_usd
            self.blocked = self.blocked or overrun
            self.on_change()
            if overrun:
                raise BudgetError("Provider usage exceeded reservation; further calls blocked")

    def fail(self, index: int) -> None:
        with self._lock:
            call = self.calls[index]
            if call.status == "pending":
                call.status = "unverified"
                self.blocked = True
                self.on_change()

    def snapshot(self) -> dict:
        with self._lock:
            components = {}
            for component in COMPONENTS:
                calls = [call for call in self.calls if call.component == component]
                known = [call for call in calls if call.status == "verified"]
                components[component] = {
                    "status": "not_called"
                    if not calls
                    else ("verified" if len(known) == len(calls) else "unverified"),
                    "input_tokens": (
                        sum(call.input_tokens for call in known if call.input_tokens is not None)
                        if len(known) == len(calls)
                        else None
                    ),
                    "output_tokens": (
                        sum(call.output_tokens for call in known if call.output_tokens is not None)
                        if len(known) == len(calls)
                        else None
                    ),
                    "known_cost_usd": (
                        str(sum((call.cost_usd for call in known), Decimal(0)))
                        if len(known) == len(calls)
                        else None
                    ),
                    "committed_or_reserved_usd": str(
                        sum(
                            (call.cost_usd if call.cost_usd is not None else call.reserved_usd)
                            for call in calls
                        )
                    ),
                }
            return {
                "scope": "this run only; not a provider billing cap",
                "limit_usd": str(self.limit),
                "committed_or_reserved_usd": str(self.committed),
                "blocked": self.blocked,
                "components": components,
                "calls": [call.model_dump(mode="json") for call in self.calls],
            }
