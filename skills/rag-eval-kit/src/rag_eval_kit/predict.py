"""Run an adapter over a dataset split and collect portable predictions; failures are recorded."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rag_eval_kit.models import EvaluationCase, EvaluationRecord


def read_cases(path: Path) -> list[EvaluationCase]:
    cases = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    cases.append(EvaluationCase.model_validate_json(line))
                except ValueError:
                    raise ValueError(f"Invalid dataset row {number}") from None
    if not cases:
        raise ValueError("Dataset is empty")
    ids = [c.question_id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Dataset question IDs must be unique")
    return cases


def run_predictions(
    cases: list[EvaluationCase],
    predict_one: Callable[[EvaluationCase], EvaluationRecord],
    *,
    concurrency: int = 1,
) -> tuple[list[EvaluationRecord], list[dict[str, str]]]:
    """Return (records, failures). A failed case is never dropped silently."""
    if not 1 <= concurrency <= 5:
        raise ValueError("Concurrency must be between 1 and 5")

    def attempt(case: EvaluationCase) -> tuple[EvaluationRecord | None, dict[str, str] | None]:
        try:
            return predict_one(case), None
        except Exception as error:
            return None, {
                "question_id": case.question_id,
                "error_type": type(error).__name__,
                "error": str(error)[:300],
            }

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(attempt, cases))
    return [r for r, _ in results if r], [f for _, f in results if f]
