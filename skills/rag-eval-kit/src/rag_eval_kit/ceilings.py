"""thresholds.yaml: ceilings the operational measurements must stay under.

Ceilings are agreed before looking at results, like pass rules. Checking them is a yes/no
comparison of recorded measurements; it does not change any score.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Ceilings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency_p95_ms: float | None = Field(default=None, gt=0)
    error_rate: float | None = Field(default=None, ge=0, le=1)
    invalid_rate: float | None = Field(default=None, ge=0, le=1)
    cost_per_query_usd: float | None = Field(default=None, ge=0)


class ThresholdsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ceilings: Ceilings


class ThresholdsError(ValueError):
    pass


def load_thresholds(path: Path) -> ThresholdsFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ThresholdsError(f"Cannot read {path.name} ({type(error).__name__})") from None
    if not isinstance(raw, dict):
        raise ThresholdsError(f"{path.name} must contain a 'ceilings' section")
    try:
        return ThresholdsFile.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise ThresholdsError(f"{path.name}: {where}: {first['msg']}") from None


def _observed(observability: dict[str, Any], name: str) -> float | None:
    block = {
        "latency_p95_ms": observability.get("latency_ms", {}).get("p95"),
        "error_rate": observability.get("error_rate", {}).get("rate"),
        "invalid_rate": observability.get("invalid_rate", {}).get("rate"),
        "cost_per_query_usd": observability.get("cost", {}).get("per_query_usd"),
    }[name]
    return None if block is None else float(block)


def check_ceilings(observability: dict[str, Any], ceilings: Ceilings) -> dict[str, Any]:
    """Compare measurements with the ceilings that were set. Unknown values never pass."""
    checks = []
    for name, limit in ceilings.model_dump().items():
        if limit is None:
            continue
        observed = _observed(observability, name)
        if observed is None:
            status = "UNASSESSABLE"
        else:
            status = "PASS" if observed <= limit else "FAIL"
        checks.append({"ceiling": name, "limit": limit, "observed": observed, "result": status})
    results = {c["result"] for c in checks}
    overall = (
        "failed" if "FAIL" in results else "unassessable" if "UNASSESSABLE" in results else "met"
    )
    notes = []
    latency = observability.get("latency_ms", {})
    if latency.get("low_sample"):
        notes.append(
            f"Latency p95 is from only {latency.get('n')} answers; with so few it is close to "
            "the slowest one."
        )
    return {"overall": overall if checks else "no_ceilings_set", "checks": checks, "notes": notes}
