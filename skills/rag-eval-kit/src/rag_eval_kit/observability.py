"""Operational measurements for a run: latency, errors, tokens and estimated cost.

Nothing here is a quality metric and nothing here feeds a score. It only summarises what the
adapters recorded about each question, so a change that makes answers better but slower, more
error-prone or more expensive is visible.
"""

import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rag_eval_kit.models import EvaluationRecord

LOW_SAMPLE = 20
LATENCY_METHOD = (
    "Client-side wall-clock time per answered question (monotonic clock, retries and back-off "
    "included), nearest-rank percentiles."
)


class Pricing(BaseModel):
    """Explicit prices for the app under test. Never taken from memory."""

    model_config = ConfigDict(extra="forbid")

    input_usd_per_million: Decimal = Field(ge=0)
    output_usd_per_million: Decimal = Field(ge=0)
    source_url: str = Field(min_length=1, max_length=2048)
    checked_on: str = Field(min_length=1, max_length=40)


class ObservabilityError(ValueError):
    pass


def load_pricing(path: Path) -> Pricing:
    try:
        return Pricing.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, InvalidOperation, ValidationError) as error:
        raise ObservabilityError(f"Invalid pricing file ({type(error).__name__})") from None


def load_failures(path: Path) -> dict[str, Any]:
    """Read the failures file written by ``ragkit predict`` ({"attempted": n, "failed": [...]})."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        failed = data["failed"]
        attempted = data["attempted"]
    except (OSError, ValueError, KeyError, TypeError):
        raise ObservabilityError("Invalid failures file") from None
    if not isinstance(failed, list) or not isinstance(attempted, int):
        raise ObservabilityError("Invalid failures file")
    return {"attempted": attempted, "failed": failed}


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation). ``values`` must not be empty."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _latency(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"status": "UNAVAILABLE", "n": 0, "reason": "No latency was recorded"}
    return {
        "status": "VERIFIED",
        "n": len(values),
        "p50": round(percentile(values, 50), 3),
        "p95": round(percentile(values, 95), 3),
        "max": round(max(values), 3),
        "low_sample": len(values) < LOW_SAMPLE,
    }


def _rate(count: int, total: int) -> float | None:
    return None if total <= 0 else count / total


def _cost(records: list[EvaluationRecord], pricing: Pricing | None) -> dict[str, Any]:
    if pricing is None:
        return {"status": "UNAVAILABLE", "reason": "No pricing file was given (--pricing)"}
    priced = [r for r in records if r.input_tokens is not None and r.output_tokens is not None]
    if not priced:
        only_total = any(r.total_tokens is not None for r in records)
        reason = (
            "The app reports total tokens only; separate input and output counts are needed "
            "to price them"
            if only_total
            else "The app did not report token counts"
        )
        return {"status": "UNAVAILABLE", "reason": reason}
    total = (
        Decimal(sum(r.input_tokens or 0 for r in priced)) * pricing.input_usd_per_million
        + Decimal(sum(r.output_tokens or 0 for r in priced)) * pricing.output_usd_per_million
    ) / Decimal(1_000_000)
    return {
        "status": "ESTIMATED" if len(priced) == len(records) else "PARTIAL",
        "records_priced": len(priced),
        "records_total": len(records),
        "estimated_usd_total": str(total),
        "per_query_usd": str(total / len(priced)),
        "pricing": {
            "input_usd_per_million": str(pricing.input_usd_per_million),
            "output_usd_per_million": str(pricing.output_usd_per_million),
            "source_url": pricing.source_url,
            "checked_on": pricing.checked_on,
        },
        "note": "An estimate from token counts and the prices you supplied; not a bill. It "
        "covers the app under test only (not the judge) and excludes hosting.",
    }


def build_observability(
    records: list[EvaluationRecord],
    *,
    counts: dict[str, Any],
    failures: dict[str, Any] | None = None,
    pricing: Pricing | None = None,
) -> dict[str, Any]:
    """Summarise latency, error rate, invalid rate, tokens and estimated cost for a run."""
    answered_ms = [r.latency_ms for r in records if r.latency_ms is not None]
    app_ms = [r.app_latency_ms for r in records if r.app_latency_ms is not None]
    warnings: list[str] = []

    if failures is None:
        errors: dict[str, Any] = {
            "status": "UNKNOWN",
            "reason": "No failures file was given (--failures), so errors cannot be counted",
            "rate": None,
        }
    else:
        failed = failures["failed"]
        attempted = len(records) + len(failed)
        if failures["attempted"] != attempted:
            warnings.append(
                f"The failures file says {failures['attempted']} questions were attempted but "
                f"{attempted} records and failures were found."
            )
        errors = {
            "status": "VERIFIED",
            "failed": len(failed),
            "timeouts": sum(1 for f in failed if f.get("kind") == "timeout"),
            "attempted": attempted,
            "rate": _rate(len(failed), attempted),
        }

    total_records = int(counts.get("total_records", len(records)))
    invalid = int(counts.get("invalid_records", 0))
    tokens_in = [r.input_tokens for r in records if r.input_tokens is not None]
    tokens_out = [r.output_tokens for r in records if r.output_tokens is not None]
    tokens_total = [r.total_tokens for r in records if r.total_tokens is not None]
    if not any((tokens_in, tokens_out, tokens_total)):
        tokens: dict[str, Any] = {
            "status": "UNAVAILABLE",
            "reason": "The app did not report tokens",
        }
    else:
        tokens = {
            "status": "REPORTED_BY_APP",
            "records_with_tokens": max(len(tokens_in), len(tokens_out), len(tokens_total)),
            "input": sum(tokens_in) if tokens_in else None,
            "output": sum(tokens_out) if tokens_out else None,
            "total": sum(tokens_total) if tokens_total else None,
        }
    if any(r.latency_ms is not None and r.latency_ms == 0 for r in records):
        warnings.append("A latency of exactly 0 ms was recorded; check the clock source.")

    return {
        "latency_ms": {**_latency(answered_ms), "method": LATENCY_METHOD},
        "app_reported_latency_ms": _latency(app_ms),
        "error_rate": errors,
        "invalid_rate": {
            "status": "VERIFIED",
            "invalid": invalid,
            "total": total_records,
            "rate": _rate(invalid, total_records),
        },
        "tokens": tokens,
        "cost": _cost(records, pricing),
        "warnings": warnings,
    }
