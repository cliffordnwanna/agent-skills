"""Offline and opt-in semantic evaluation for portable prediction records."""

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import UTC, datetime
from math import comb
from statistics import mean
from typing import Any
from uuid import uuid4

from rag_eval_kit import __version__
from rag_eval_kit.models import EvaluationRecord

LEXICAL_METRICS = ("hit_at_1", "hit_at_3", "recall_at_3", "mrr", "abstention_accuracy")
SEMANTIC_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "contextual_recall",
    "contextual_precision",
    "contextual_relevancy",
)


def _retrieval_metrics(record: EvaluationRecord) -> dict[str, float | None]:
    expected = set(record.expected_source_ids)
    if not expected:
        return {key: None for key in LEXICAL_METRICS[:4]}
    retrieved = record.retrieved_source_ids
    relevant_ranks = [
        index for index, source_id in enumerate(retrieved, 1) if source_id in expected
    ]
    return {
        "hit_at_1": float(bool(relevant_ranks and relevant_ranks[0] == 1)),
        "hit_at_3": float(any(rank <= 3 for rank in relevant_ranks)),
        "recall_at_3": len({retrieved[index - 1] for index in relevant_ranks if index <= 3})
        / len(expected),
        "mrr": 1 / relevant_ranks[0] if relevant_ranks else 0.0,
    }


def _abstention_metric(record: EvaluationRecord) -> float | None:
    if record.abstained is None or record.category is None:
        return None
    expected_abstention = record.category == "unanswerable"
    return float(record.abstained == expected_abstention)


def _summary(values: list[float]) -> dict[str, float | int | None | str]:
    if not values:
        return {"score": None, "assessed": 0, "status": "UNASSESSABLE"}
    return {"score": mean(values), "assessed": len(values), "status": "VERIFIED"}


def evaluate_lexical(
    records: list[EvaluationRecord],
    *,
    target_revision: str,
    dataset_hash: str,
    corpus_hash: str,
) -> dict[str, Any]:
    if not records:
        raise ValueError("Evaluation requires at least one prediction record")
    valid: list[EvaluationRecord] = []
    invalid: list[dict[str, Any]] = []
    for record in records:
        reason = None
        if record.retrieval_mode != "lexical":
            reason = f"Expected lexical retrieval; received {record.retrieval_mode}"
        elif record.target_revision != target_revision:
            reason = "Prediction target revision does not match the requested revision"
        if reason:
            invalid.append(
                {"question_id": record.question_id, "repeat": record.repeat, "reason": reason}
            )
        else:
            valid.append(record)

    per_question: dict[str, dict[str, Any]] = {}
    values: dict[str, list[float]] = defaultdict(list)
    grouped: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in valid:
        grouped[record.question_id].append(record)
    for question_id, question_records in sorted(grouped.items()):
        by_metric: dict[str, list[float]] = defaultdict(list)
        for record in question_records:
            metrics = _retrieval_metrics(record)
            abstention = _abstention_metric(record)
            metrics["abstention_accuracy"] = abstention
            for name, value in metrics.items():
                if value is not None:
                    by_metric[name].append(value)
        question_metrics = {
            name: mean(metric_values) if metric_values else None
            for name, metric_values in by_metric.items()
        }
        per_question[question_id] = {"metrics": question_metrics}
        for name, value in question_metrics.items():
            if value is not None:
                values[name].append(value)

    metric_names = LEXICAL_METRICS
    return {
        "schema_version": 1,
        "run_id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "tool_version": __version__,
        "status": "completed" if valid else "no_valid_records",
        "retrieval_mode": "lexical",
        "target_revision": target_revision,
        "dataset_hash": dataset_hash,
        "corpus_hash": corpus_hash,
        "judge": None,
        "input_sha256": _records_hash(records),
        "counts": {
            "total_records": len(records),
            "valid_records": len(valid),
            "invalid_records": len(invalid),
            "questions": len(per_question),
            "unassessable_questions": sum(
                all(value is None for value in item["metrics"].values())
                for item in per_question.values()
            ),
        },
        "metrics": {name: _summary(values[name]) for name in metric_names},
        "per_question": per_question,
        "invalid_records": invalid,
        "warnings": [
            "Lexical retrieval metrics do not measure semantic relevance or answer quality."
        ],
    }


def evaluate_semantic(
    records: list[EvaluationRecord],
    *,
    target_revision: str,
    dataset_hash: str,
    corpus_hash: str,
    judge: Any,
    repeats: int = 3,
) -> dict[str, Any]:
    if not records:
        raise ValueError("Evaluation requires at least one prediction record")
    if repeats < 1 or repeats > 5:
        raise ValueError("Semantic metric repeats must be between 1 and 5")

    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    metric_types = (
        ("faithfulness", FaithfulnessMetric),
        ("answer_relevancy", AnswerRelevancyMetric),
        ("contextual_recall", ContextualRecallMetric),
        ("contextual_precision", ContextualPrecisionMetric),
        ("contextual_relevancy", ContextualRelevancyMetric),
    )
    valid: list[EvaluationRecord] = []
    invalid: list[dict[str, Any]] = []
    unassessable: list[dict[str, Any]] = []
    for record in records:
        reason = None
        if record.retrieval_mode != "semantic":
            reason = f"Semantic track requires semantic retrieval; received {record.retrieval_mode}"
        elif record.target_revision != target_revision:
            reason = "Prediction target revision does not match the requested revision"
        if reason:
            invalid.append(
                {"question_id": record.question_id, "repeat": record.repeat, "reason": reason}
            )
        elif not record.answer:
            unassessable.append(
                {"question_id": record.question_id, "repeat": record.repeat, "reason": "No answer"}
            )
        else:
            valid.append(record)

    question_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    unassessable_metrics: list[dict[str, str]] = []
    for record in valid:
        abstention = _abstention_metric(record)
        if abstention is not None:
            question_scores[record.question_id]["abstention_accuracy"].append(abstention)
        test_case = LLMTestCase(
            input=record.question,
            actual_output=record.answer,
            expected_output=record.reference_answer or "",
            retrieval_context=record.retrieved_contexts,
        )
        for name, metric_type in metric_types:
            if name != "answer_relevancy" and (
                not record.reference_evidence or not record.retrieved_contexts
            ):
                unassessable_metrics.append(
                    {
                        "question_id": record.question_id,
                        "metric": name,
                        "reason": "Reference evidence and retrieved contexts are required",
                    }
                )
                continue
            if (
                name in {"contextual_recall", "contextual_precision"}
                and not record.reference_answer
            ):
                unassessable_metrics.append(
                    {
                        "question_id": record.question_id,
                        "metric": name,
                        "reason": "A reference answer is required",
                    }
                )
                continue
            for _ in range(repeats):
                metric = metric_type(
                    model=judge,
                    eval_mode="llm",
                    async_mode=False,
                    include_reason=False,
                )
                metric.measure(test_case, _show_indicator=False)
                score = metric.score
                if score is None or not math.isfinite(float(score)):
                    raise ValueError(f"{name} returned no finite score for {record.question_id}")
                question_scores[record.question_id][name].append(float(score))

    per_question = {
        question_id: {
            "metrics": {name: mean(scores) for name, scores in sorted(metric_values.items())},
            "metric_repeats": {name: scores for name, scores in sorted(metric_values.items())},
        }
        for question_id, metric_values in sorted(question_scores.items())
    }
    aggregate: dict[str, dict[str, Any]] = {}
    for name in SEMANTIC_METRICS:
        scores = [
            score
            for item in per_question.values()
            if (score := item["metrics"].get(name)) is not None
        ]
        repeated_scores = [
            score
            for item in per_question.values()
            for score in item["metric_repeats"].get(name, [])
        ]
        aggregate[name] = {
            **_summary(scores),
            "repeats_per_question": repeats,
            "repeat_spread_min": min(repeated_scores) if repeated_scores else None,
            "repeat_spread_max": max(repeated_scores) if repeated_scores else None,
        }
    abstention_values = [
        score
        for item in per_question.values()
        if (score := item["metrics"].get("abstention_accuracy")) is not None
    ]
    aggregate["abstention_accuracy"] = _summary(abstention_values)
    ledger = getattr(judge, "ledger", None)
    return {
        "schema_version": 1,
        "run_id": str(uuid4()),
        "created_at": datetime.now(UTC).isoformat(),
        "tool_version": __version__,
        "status": "completed" if valid else "no_assessable_records",
        "retrieval_mode": "semantic",
        "target_revision": target_revision,
        "dataset_hash": dataset_hash,
        "corpus_hash": corpus_hash,
        "judge": {
            "model": judge.get_model_name(),
            "deepeval_version": _deepeval_version(),
        },
        "input_sha256": _records_hash(records),
        "counts": {
            "total_records": len(records),
            "valid_records": len(valid),
            "invalid_records": len(invalid),
            "unassessable_records": len(unassessable),
            "unassessable_metric_cases": len(unassessable_metrics),
            "questions": len(per_question),
        },
        "metrics": aggregate,
        "per_question": per_question,
        "invalid_records": invalid,
        "unassessable_records": unassessable,
        "unassessable_metrics": unassessable_metrics,
        "budget": ledger.snapshot() if ledger is not None else None,
        "warnings": [
            "LLM judge scores are estimates, not ground truth.",
            f"Each judge metric was run {repeats} times; repeat spread is reported.",
        ],
    }


def compare_runs(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_incompatible: bool = False,
    pass_metric: str | None = None,
    pass_threshold: float | None = None,
    bootstrap_samples: int = 10_000,
    seed: int = 2026,
) -> dict[str, Any]:
    if baseline.get("status") != "completed" or candidate.get("status") != "completed":
        raise ValueError("Both runs must be completed before comparison")
    compatibility_fields = ("dataset_hash", "corpus_hash", "retrieval_mode", "judge")
    mismatches = [
        field for field in compatibility_fields if baseline.get(field) != candidate.get(field)
    ]
    if mismatches and not allow_incompatible:
        raise ValueError(f"Runs are incompatible: {', '.join(mismatches)}")
    if pass_metric is not None and (pass_threshold is None or not 0 <= pass_threshold <= 1):
        raise ValueError("A pass threshold between 0 and 1 is required with --pass-metric")
    if pass_metric is None and pass_threshold is not None:
        raise ValueError("--pass-threshold requires --pass-metric")
    if bootstrap_samples < 100:
        raise ValueError("At least 100 paired bootstrap samples are required")

    before = baseline.get("per_question", {})
    after = candidate.get("per_question", {})
    paired_ids = sorted(set(before) & set(after))
    if not paired_ids:
        raise ValueError("Runs have no paired question IDs")
    common_metrics = sorted(set(baseline.get("metrics", {})) & set(candidate.get("metrics", {})))
    metric_deltas: dict[str, Any] = {}
    for name in common_metrics:
        deltas = [
            after[question_id]["metrics"][name] - before[question_id]["metrics"][name]
            for question_id in paired_ids
            if before[question_id]["metrics"].get(name) is not None
            and after[question_id]["metrics"].get(name) is not None
        ]
        metric_deltas[name] = {
            "paired_questions": len(deltas),
            "mean_delta": mean(deltas) if deltas else None,
            "bootstrap_95_ci": _bootstrap_mean_ci(deltas, bootstrap_samples, seed)
            if deltas
            else None,
        }

    paired_test = None
    if pass_metric is not None:
        if pass_metric not in common_metrics:
            raise ValueError(f"Pass metric is unavailable in both runs: {pass_metric}")
        pairs = [
            (
                before[question_id]["metrics"].get(pass_metric),
                after[question_id]["metrics"].get(pass_metric),
            )
            for question_id in paired_ids
        ]
        pairs = [(old, new) for old, new in pairs if old is not None and new is not None]
        old_passes = [old >= pass_threshold for old, _ in pairs]
        new_passes = [new >= pass_threshold for _, new in pairs]
        discordant_before_pass = sum(
            old and not new for old, new in zip(old_passes, new_passes, strict=True)
        )
        discordant_after_pass = sum(
            not old and new for old, new in zip(old_passes, new_passes, strict=True)
        )
        paired_test = {
            "metric": pass_metric,
            "threshold": pass_threshold,
            "paired_questions": len(pairs),
            "baseline_pass_rate_wilson_95_ci": _wilson_interval(sum(old_passes), len(pairs)),
            "candidate_pass_rate_wilson_95_ci": _wilson_interval(sum(new_passes), len(pairs)),
            "mcnemar_exact_two_sided_p": _mcnemar_exact(
                discordant_before_pass, discordant_after_pass
            ),
            "baseline_passes": sum(old_passes),
            "candidate_passes": sum(new_passes),
            "discordant_baseline_only": discordant_before_pass,
            "discordant_candidate_only": discordant_after_pass,
        }
    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "baseline_run_id": baseline.get("run_id"),
        "candidate_run_id": candidate.get("run_id"),
        "compatible": not mismatches,
        "compatibility_overridden": bool(mismatches and allow_incompatible),
        "compatibility_mismatches": mismatches,
        "paired_questions": len(paired_ids),
        "unpaired_baseline_questions": len(set(before) - set(after)),
        "unpaired_candidate_questions": len(set(after) - set(before)),
        "metric_deltas": metric_deltas,
        "paired_pass_test": paired_test,
        "warnings": [
            "A small held-out set is exploratory; statistical intervals do not establish "
            "broad generalization."
        ],
    }


def _records_hash(records: list[EvaluationRecord]) -> str:
    content = "\n".join(record.model_dump_json() for record in records).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _deepeval_version() -> str:
    from importlib.metadata import version

    return version("deepeval")


def _bootstrap_mean_ci(values: list[float], samples: int, seed: int) -> list[float]:
    randomizer = random.Random(seed)
    size = len(values)
    means = sorted(mean(randomizer.choices(values, k=size)) for _ in range(samples))
    lower = means[max(0, int(0.025 * samples))]
    upper = means[min(samples - 1, int(0.975 * samples))]
    return [lower, upper]


def _mcnemar_exact(before_only: int, after_only: int) -> float | None:
    discordant = before_only + after_only
    if discordant == 0:
        return 1.0
    tail = sum(comb(discordant, index) for index in range(min(before_only, after_only) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def _wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    return [max(0.0, center - margin / denominator), min(1.0, center + margin / denominator)]


def write_run(path: Any, run: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(run, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
