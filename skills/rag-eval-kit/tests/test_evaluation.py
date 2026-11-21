import json

import pytest
from pydantic import ValidationError

from rag_eval_kit.evaluation import compare_runs, evaluate_lexical, evaluate_semantic
from rag_eval_kit.models import EvaluationRecord
from rag_eval_kit.reporting import markdown_report

REVISION = "a" * 40
DATASET_HASH = "b" * 64
CORPUS_HASH = "c" * 64


def record(**changes):
    values = {
        "question_id": "q1",
        "question": "What is the answer?",
        "answer": "The answer is documented.",
        "retrieved_contexts": ["Full source evidence."],
        "retrieved_source_ids": ["source-a", "source-b"],
        "reference_answer": "The documented answer.",
        "reference_evidence": ["Full source evidence."],
        "expected_source_ids": ["source-a"],
        "category": "direct",
        "abstained": False,
        "target_revision": REVISION,
        "retrieval_mode": "lexical",
    }
    values.update(changes)
    return EvaluationRecord.model_validate(values)


def run(metrics, *, mode="lexical", judge=None):
    metric_names = {name for item in metrics.values() for name in item.get("metrics", {})}
    return {
        "run_id": "run",
        "status": "completed",
        "dataset_hash": DATASET_HASH,
        "corpus_hash": CORPUS_HASH,
        "retrieval_mode": mode,
        "judge": judge,
        "metrics": {name: {"score": 0.5} for name in metric_names},
        "per_question": metrics,
    }


def test_lexical_metrics_and_invalid_modes_are_separated():
    report = evaluate_lexical(
        [
            record(),
            record(question_id="q2", retrieved_source_ids=["other"]),
            record(question_id="q3", retrieval_mode="semantic"),
        ],
        target_revision=REVISION,
        dataset_hash=DATASET_HASH,
        corpus_hash=CORPUS_HASH,
    )
    assert report["retrieval_mode"] == "lexical"
    assert report["counts"] == {
        "total_records": 3,
        "valid_records": 2,
        "invalid_records": 1,
        "questions": 2,
        "unassessable_questions": 0,
    }
    assert report["metrics"]["hit_at_1"]["score"] == 0.5
    assert report["metrics"]["hit_at_3"]["score"] == 0.5
    assert report["metrics"]["recall_at_3"]["score"] == 0.5
    assert report["metrics"]["mrr"]["score"] == 0.5
    assert report["metrics"]["abstention_accuracy"]["score"] == 1
    assert report["invalid_records"][0]["question_id"] == "q3"


def test_lexical_metrics_report_missing_labels_as_unassessable():
    report = evaluate_lexical(
        [record(expected_source_ids=[])],
        target_revision=REVISION,
        dataset_hash=DATASET_HASH,
        corpus_hash=CORPUS_HASH,
    )
    assert report["metrics"]["hit_at_1"]["score"] is None
    assert report["metrics"]["hit_at_1"]["status"] == "UNASSESSABLE"


def test_semantic_track_requires_semantic_mode_and_marks_missing_evidence():
    from rag_eval_kit.offline import OfflineSchemaJudge

    report = evaluate_semantic(
        [
            record(retrieval_mode="lexical"),
            record(question_id="q2", retrieval_mode="semantic", reference_evidence=[]),
        ],
        target_revision=REVISION,
        dataset_hash=DATASET_HASH,
        corpus_hash=CORPUS_HASH,
        judge=OfflineSchemaJudge(),
    )
    assert report["counts"]["invalid_records"] == 1
    assert report["counts"]["valid_records"] == 1
    assert all(
        report["metrics"][name]["score"] is None
        for name in (
            "faithfulness",
            "contextual_recall",
            "contextual_precision",
            "contextual_relevancy",
        )
    )
    assert any("Reference evidence" in item["reason"] for item in report["unassessable_metrics"])


def test_semantic_metrics_repeat_three_times_without_network(monkeypatch):
    import deepeval.metrics

    class FakeMetric:
        def __init__(self, **kwargs):
            self.score = None

        def measure(self, test_case, _show_indicator=False):
            self.score = 0.7

    for metric_name in (
        "AnswerRelevancyMetric",
        "ContextualPrecisionMetric",
        "ContextualRecallMetric",
        "ContextualRelevancyMetric",
        "FaithfulnessMetric",
    ):
        monkeypatch.setattr(deepeval.metrics, metric_name, FakeMetric)

    from rag_eval_kit.offline import OfflineSchemaJudge

    report = evaluate_semantic(
        [record(retrieval_mode="semantic")],
        target_revision=REVISION,
        dataset_hash=DATASET_HASH,
        corpus_hash=CORPUS_HASH,
        judge=OfflineSchemaJudge(),
        repeats=3,
    )
    assert report["metrics"]["faithfulness"]["score"] == 0.7
    assert report["metrics"]["faithfulness"]["repeat_spread_min"] == 0.7
    assert report["metrics"]["faithfulness"]["repeats_per_question"] == 3
    assert len(report["per_question"]["q1"]["metric_repeats"]["faithfulness"]) == 3


def test_compare_blocks_incompatible_runs_and_reports_paired_statistics():
    before = run(
        {
            "q1": {"metrics": {"hit_at_3": 0.0}},
            "q2": {"metrics": {"hit_at_3": 1.0}},
        }
    )
    after = run(
        {
            "q1": {"metrics": {"hit_at_3": 1.0}},
            "q2": {"metrics": {"hit_at_3": 1.0}},
        }
    )
    after["run_id"] = "candidate"
    with pytest.raises(ValueError, match="incompatible"):
        compare_runs(before, {**after, "judge": {"model": "other"}})

    result = compare_runs(
        before,
        after,
        pass_metric="hit_at_3",
        pass_threshold=1.0,
        bootstrap_samples=1000,
        seed=7,
    )
    assert result["metric_deltas"]["hit_at_3"]["mean_delta"] == 0.5
    assert result["paired_pass_test"]["baseline_pass_rate_wilson_95_ci"]
    assert result["paired_pass_test"]["candidate_passes"] == 2
    assert result["paired_pass_test"]["mcnemar_exact_two_sided_p"] == 1
    assert result["warnings"]


def test_compare_incompatibility_override_is_explicit():
    before = run({"q1": {"metrics": {"mrr": 0.2}}})
    after = run({"q1": {"metrics": {"mrr": 0.8}}}, mode="semantic")
    result = compare_runs(before, after, allow_incompatible=True, bootstrap_samples=100)
    assert result["compatibility_overridden"] is True
    assert "retrieval_mode" in result["compatibility_mismatches"]


def test_markdown_report_does_not_expose_predictions():
    text = markdown_report(
        {
            "run_id": "safe-run",
            "retrieval_mode": "lexical",
            "target_revision": REVISION,
            "dataset_hash": DATASET_HASH,
            "corpus_hash": CORPUS_HASH,
            "judge": None,
            "metrics": {"hit_at_1": {"score": 0.75, "assessed": 4, "status": "VERIFIED"}},
            "counts": {"total_records": 4, "valid_records": 4, "invalid_records": 0},
            "warnings": ["Lexical only."],
            "per_question": {"private-question": {"answer": "private-answer"}},
        }
    )
    assert "0.7500" in text
    assert "private-question" not in text
    assert "private-answer" not in text
    json.dumps({"report": text})


def test_record_validation_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        record(retrieval_mode="unknown")
