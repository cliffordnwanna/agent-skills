"""Small real-framework compatibility run; not the future RAG evaluation runner."""

import hashlib
import json
import platform
from importlib.metadata import version
from time import perf_counter
from typing import Any

from rag_eval_kit.fixtures import EXAMPLES
from rag_eval_kit.privacy import configure_local_runtime

configure_local_runtime()

from deepeval.metrics import (  # noqa: E402
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.synthesizer import Synthesizer  # noqa: E402
from deepeval.synthesizer.config import EvolutionConfig, FiltrationConfig  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402

METRICS = (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
)


def versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        **{
            name: version(name)
            for name in ("rag-eval-kit", "deepeval", "openai", "pydantic", "httpx")
        },
    }


def run_spike(judge: Any, offline: bool, progress: dict | None = None) -> dict:
    report = progress if progress is not None else {}
    report.update(
        {
            "kind": "framework_compatibility_only",
            "versions": versions(),
            "mode": "offline-schema-fixture" if offline else "live-openai",
            "quality_evidence": False,
            "judge": judge.get_model_name(),
            "fixture_sha256": hashlib.sha256(
                json.dumps(EXAMPLES, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "model_compatibility": "UNVERIFIED" if offline else "PENDING",
            "metrics": [],
            "synthesizer": {"status": "not_run"},
        }
    )
    if not offline:
        # Minimal availability check goes through the same reservation and usage accounting.
        response = judge.generate("Reply with the word ready.")
        if not isinstance(response, str) or not response.strip():
            raise RuntimeError("Model availability check returned no text")
        report["model_compatibility"] = "VERIFIED minimal text request; metrics pending"
    for example in EXAMPLES:
        case = LLMTestCase(**{key: value for key, value in example.items() if key != "id"})
        for metric_type in METRICS:
            started = perf_counter()
            metric = metric_type(
                model=judge,
                eval_mode="llm",
                async_mode=False,
                include_reason=True,
            )
            metric.measure(case, _show_indicator=False)
            report["metrics"].append(
                {
                    "case_id": example["id"],
                    "metric": metric_type.__name__,
                    "status": "VERIFIED framework execution"
                    if offline
                    else "VERIFIED live execution",
                    "score": None if offline else metric.score,
                    "reason": "Withheld: canned fixture is not quality evidence"
                    if offline
                    else metric.reason,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                }
            )
    synthesizer = Synthesizer(
        model=judge,
        async_mode=False,
        max_concurrent=1,
        filtration_config=FiltrationConfig(critic_model=judge, max_quality_retries=1),
        evolution_config=EvolutionConfig(num_evolutions=0),
        cost_tracking=False,
    )
    candidates = synthesizer.generate_goldens_from_contexts(
        contexts=[example["retrieval_context"] for example in EXAMPLES],
        include_expected_output=True,
        max_goldens_per_context=1,
        _send_data=False,
    )
    report["synthesizer"] = {
        "status": "VERIFIED framework execution" if offline else "VERIFIED live execution",
        "candidate_count": len(candidates),
        "human_review": "required; NOT approved goldens",
        "candidates": [
            {
                "input": item.input,
                "expected_output": item.expected_output,
                "context": item.context,
                "approved": False,
            }
            for item in candidates
        ],
    }
    if len(candidates) != len(EXAMPLES):
        raise RuntimeError("Synthesizer returned an unexpected number of candidates")
    if offline:
        report["fixture_model_calls"] = len(judge.calls)
    else:
        report["model_compatibility"] = (
            "VERIFIED for this model/configuration and these fixtures only"
        )
    return report
