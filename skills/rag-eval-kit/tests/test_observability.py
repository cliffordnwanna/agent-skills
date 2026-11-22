"""Latency, errors, tokens, cost, ceilings and document-level Hit@k. No paid calls."""

import json
import time

import httpx
import pytest
from typer.testing import CliRunner

from rag_eval_kit.adapters.base import AdapterError
from rag_eval_kit.adapters.builder import BuilderHTTPAdapter, BuilderHTTPConfig
from rag_eval_kit.adapters.files import write_jsonl
from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig
from rag_eval_kit.ceilings import (
    Ceilings,
    ThresholdsError,
    check_ceilings,
    load_thresholds,
)
from rag_eval_kit.cli import app
from rag_eval_kit.evaluation import compare_runs, evaluate_lexical
from rag_eval_kit.mock_server import demo_cases, make_server, serve_in_thread
from rag_eval_kit.models import CorpusDocument, EvaluationRecord
from rag_eval_kit.observability import (
    ObservabilityError,
    Pricing,
    build_observability,
    load_failures,
    load_pricing,
    percentile,
)
from rag_eval_kit.predict import run_predictions

runner = CliRunner()
HASH = "a" * 64
CASE = demo_cases()[0]


def rec(qid="q-1", **extra):
    data = {
        "question_id": qid,
        "question": "Which port does the alpha service use?",
        "answer": "Port 8080.",
        "retrieved_source_ids": ["alpha"],
        "expected_source_ids": ["alpha"],
        "category": "direct",
        "target_revision": "rev",
        "retrieval_mode": "lexical",
    }
    data.update(extra)
    return EvaluationRecord.model_validate(data)


# ------------------------------------------------------------------ percentiles
def test_nearest_rank_percentiles():
    ten = [float(x) for x in range(1, 11)]
    assert percentile(ten, 50) == 5 and percentile(ten, 95) == 10
    assert percentile([7.0], 95) == 7.0
    assert percentile([9.0, 1.0, 5.0], 50) == 5.0  # unsorted input is fine
    hundred = [float(x) for x in range(1, 101)]
    assert percentile(hundred, 95) == 95 and percentile(hundred, 50) == 50


# ---------------------------------------------------------------- observability
def test_latency_error_invalid_and_token_summaries():
    records = [
        rec(f"q-{i}", latency_ms=float(100 * i), app_latency_ms=float(10 * i)) for i in range(1, 5)
    ]
    failures = {
        "attempted": 5,
        "failed": [{"question_id": "q-9", "kind": "timeout", "latency_ms": 30000.0}],
    }
    obs = build_observability(
        records, counts={"total_records": 4, "invalid_records": 1}, failures=failures
    )
    assert obs["latency_ms"]["p50"] == 200 and obs["latency_ms"]["p95"] == 400
    assert obs["latency_ms"]["n"] == 4 and obs["latency_ms"]["low_sample"] is True
    assert obs["app_reported_latency_ms"]["p95"] == 40
    assert obs["error_rate"] == {
        "status": "VERIFIED", "failed": 1, "timeouts": 1, "attempted": 5, "rate": 0.2,
    }  # fmt: skip
    assert obs["invalid_rate"]["rate"] == 0.25
    assert obs["tokens"]["status"] == "UNAVAILABLE"
    assert obs["warnings"] == []


def test_error_rate_is_unknown_without_a_failures_file_and_unavailable_without_latency():
    obs = build_observability([rec()], counts={"total_records": 1, "invalid_records": 0})
    assert obs["error_rate"]["status"] == "UNKNOWN" and obs["error_rate"]["rate"] is None
    assert obs["latency_ms"]["status"] == "UNAVAILABLE"


def test_mismatched_attempt_counts_are_flagged():
    failures = {"attempted": 9, "failed": []}
    obs = build_observability(
        [rec()], counts={"total_records": 1, "invalid_records": 0}, failures=failures
    )
    assert any("attempted" in w for w in obs["warnings"])


PRICING = Pricing(
    input_usd_per_million="0.5",
    output_usd_per_million="2.0",
    source_url="https://example.test/prices",
    checked_on="2026-11-22",
)


def test_cost_is_estimated_only_from_explicit_prices_and_split_token_counts():
    counts = {"total_records": 2, "invalid_records": 0}
    none = build_observability([rec()], counts=counts)
    assert none["cost"]["status"] == "UNAVAILABLE" and "--pricing" in none["cost"]["reason"]

    total_only = build_observability([rec(total_tokens=900)], counts=counts, pricing=PRICING)
    assert "total tokens only" in total_only["cost"]["reason"]
    assert total_only["tokens"]["status"] == "REPORTED_BY_APP"

    priced = [
        rec("a", input_tokens=1000, output_tokens=500),
        rec("b", input_tokens=1000, output_tokens=500),
    ]
    full = build_observability(priced, counts=counts, pricing=PRICING)["cost"]
    assert full["status"] == "ESTIMATED"
    assert float(full["estimated_usd_total"]) == pytest.approx(0.003)  # (2000*0.5 + 1000*2) / 1e6
    assert float(full["per_query_usd"]) == pytest.approx(0.0015)

    partly = build_observability(priced[:1] + [rec("c")], counts=counts, pricing=PRICING)["cost"]
    assert partly["status"] == "PARTIAL" and partly["records_priced"] == 1


def test_loaders_reject_bad_files(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ObservabilityError):
        load_pricing(bad)
    with pytest.raises(ObservabilityError):
        load_failures(bad)
    good = tmp_path / "f.json"
    good.write_text(json.dumps({"attempted": 3, "failed": []}), encoding="utf-8")
    assert load_failures(good)["attempted"] == 3


# --------------------------------------------------------------------- ceilings
def test_thresholds_file_is_validated(tmp_path):
    path = tmp_path / "thresholds.yaml"
    path.write_text("ceilings:\n  latency_p95_ms: 4000\n  error_rate: 0.02\n", encoding="utf-8")
    assert load_thresholds(path).ceilings.latency_p95_ms == 4000
    for text, word in [
        ("ceilings:\n  latency_p95: 4000\n", "latency_p95"),  # typo in a ceiling name
        ("ceilings:\n  error_rate: 2\n", "error_rate"),
        ("ceilings:\n  latency_p95_ms: -1\n", "latency_p95_ms"),
        ("floors:\n  x: 1\n", "ceilings"),  # no ceilings section: reported as required
        ("just text", "ceilings"),
    ]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ThresholdsError, match=word):
            load_thresholds(path)


def test_ceiling_results_pass_fail_and_never_pass_unknowns():
    obs = build_observability(
        [rec(f"q-{i}", latency_ms=1000.0 * i) for i in range(1, 4)],
        counts={"total_records": 3, "invalid_records": 0},
        failures={"attempted": 3, "failed": []},
    )
    met = check_ceilings(obs, Ceilings(latency_p95_ms=5000, error_rate=0.0, invalid_rate=0.0))
    assert met["overall"] == "met" and {c["result"] for c in met["checks"]} == {"PASS"}

    failed = check_ceilings(obs, Ceilings(latency_p95_ms=2000))
    assert failed["overall"] == "failed" and failed["checks"][0]["observed"] == 3000
    assert any("only 3 answers" in note for note in failed["notes"])

    unknown = check_ceilings(obs, Ceilings(cost_per_query_usd=0.01))  # no pricing, so no cost
    assert unknown["overall"] == "unassessable"
    assert unknown["checks"][0]["result"] == "UNASSESSABLE"
    assert check_ceilings(obs, Ceilings())["overall"] == "no_ceilings_set"


# --------------------------------------------------------------------- adapters
def adapter(handler, **config):
    cfg = GenericHTTPConfig(base_url="http://app.test", retry_backoff_seconds=0, **config)
    return GenericHTTPAdapter(cfg, httpx.Client(transport=httpx.MockTransport(handler)))


def ok_body(**extra):
    return {"answer": "Port 8080.", "retrieved_contexts": ["x"], "retrieved_source_ids": ["alpha"],
            "retrieval_mode": "lexical", **extra}  # fmt: skip


def test_generic_adapter_records_wall_clock_attempts_and_app_reported_usage():
    def handler(request):
        time.sleep(0.05)
        return httpx.Response(
            200,
            json=ok_body(usage={"in": 120, "out": 30, "ms": 41.5}, odd={"in": "many"}),
        )

    cfg = {
        "input_tokens_path": "usage.in",
        "output_tokens_path": "usage.out",
        "app_latency_ms_path": "usage.ms",
        "total_tokens_path": "usage.missing",
    }
    with adapter(handler, **cfg) as a:
        record = a.predict(CASE, "rev")
    assert record.latency_ms >= 45 and record.attempts == 1
    assert (record.input_tokens, record.output_tokens, record.app_latency_ms) == (120, 30, 41.5)
    assert record.total_tokens is None  # optional field absent: not an error


def test_unusable_usage_values_become_none_without_failing_the_question():
    def handler(request):
        return httpx.Response(200, json=ok_body(odd={"in": "many", "neg": -5, "flag": True}))

    cfg = {
        "input_tokens_path": "odd.in",
        "output_tokens_path": "odd.neg",
        "total_tokens_path": "odd.flag",
    }
    with adapter(handler, **cfg) as a:
        record = a.predict(CASE, "rev")
    assert (record.input_tokens, record.output_tokens, record.total_tokens) == (None, None, None)


def test_latency_includes_retries_and_counts_attempts():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json=ok_body())

    with adapter(handler, max_retries=2) as a:
        record = a.predict(CASE, "rev")
    assert record.attempts == 3


@pytest.mark.parametrize(
    "error,kind",
    [(httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectError("down"), "connection")],
)
def test_failures_carry_a_kind(error, kind):
    def handler(request):
        raise error

    with adapter(handler, max_retries=0) as a:
        with pytest.raises(AdapterError) as caught:
            a.predict(CASE, "rev")
    assert caught.value.kind == kind


def test_http_status_errors_have_the_default_kind():
    with adapter(lambda r: httpx.Response(500), max_retries=0) as a:
        with pytest.raises(AdapterError) as caught:
            a.predict(CASE, "rev")
    assert caught.value.kind == "error"


def test_run_predictions_times_adapters_that_do_not_and_describes_failures():
    def predict_one(case):
        if case.question_id == "demo-02":
            raise AdapterError("HTTP request failed (ReadTimeout)", kind="timeout")
        return rec(case.question_id)

    records, failures = run_predictions(demo_cases(), predict_one)
    assert len(records) == 2 and all(
        r.latency_ms is not None and r.latency_ms >= 0 for r in records
    )
    assert failures[0]["kind"] == "timeout" and failures[0]["latency_ms"] >= 0
    assert failures[0]["question_id"] == "demo-02"


def test_builder_adapter_times_only_the_chat_call_and_reads_one_turn_analytics():
    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"mode": "demo"})
        if request.url.path == "/api/chat":
            time.sleep(0.05)
            return httpx.Response(
                200,
                json={
                    "reply": "r", "mode": "demo", "retrievalMode": "lexical",
                    "chunks": [{"preview": "p", "knowledgeId": "body"}],
                    "analytics": {"messages": 1, "avgResponseTime": 0.0123, "totalTokens": 77},
                },
            )  # fmt: skip
        time.sleep(0.2)  # ingest and cleanup are slow, and must not be counted
        return httpx.Response(200, json={"success": True})

    corpus = [
        CorpusDocument(
            source_id="body", title="Body", content="text", source_url="u", source_path="b.md",
            source_sha256="b" * 64, content_sha256="c" * 64,
        )
    ]  # fmt: skip
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with BuilderHTTPAdapter(BuilderHTTPConfig(base_url="http://builder.local"), client) as b:
        record = b.predict(CASE, corpus, "rev", require_semantic=False)
    assert 45 <= record.latency_ms < 190  # the 50 ms chat call, not the 200 ms setup calls
    assert record.total_tokens == 77 and record.app_latency_ms == pytest.approx(12.3)
    assert record.attempts == 1


# ----------------------------------------------------------- document-level Hit@k
def hit_run(retrieved, expected, level):
    record = rec(retrieved_source_ids=retrieved, expected_source_ids=expected)
    run = evaluate_lexical(
        [record], target_revision="rev", dataset_hash=HASH, corpus_hash=HASH, hit_level=level
    )
    return run, {k: v["score"] for k, v in run["metrics"].items()}


def test_document_level_merges_repeated_chunks_and_is_the_default():
    retrieved = ["a", "a", "a", "b"]  # one document fills three slots; the right one is 4th
    _, document = hit_run(retrieved, ["b"], "document")
    _, chunk = hit_run(retrieved, ["b"], "chunk")
    assert document["hit_at_3"] == 1.0 and document["mrr"] == 0.5
    assert chunk["hit_at_3"] == 0.0 and chunk["mrr"] == 0.25
    default = evaluate_lexical(
        [rec(retrieved_source_ids=retrieved, expected_source_ids=["b"])],
        target_revision="rev", dataset_hash=HASH, corpus_hash=HASH,
    )  # fmt: skip
    assert default["hit_level"] == "document"
    assert any("document-level" in w for w in default["warnings"])


def test_document_level_keeps_first_position_and_recall_denominator():
    _, scores = hit_run(["x", "x", "y", "x"], ["y", "z"], "document")
    assert scores["hit_at_1"] == 0.0 and scores["hit_at_3"] == 1.0
    assert scores["recall_at_3"] == 0.5 and scores["mrr"] == 0.5


def test_unknown_hit_level_is_rejected():
    with pytest.raises(ValueError, match="hit_level"):
        hit_run(["a"], ["a"], "paragraph")


def test_runs_with_different_hit_levels_are_not_comparable():
    document, _ = hit_run(["a", "a", "b"], ["b"], "document")
    chunk, _ = hit_run(["a", "a", "b"], ["b"], "chunk")
    with pytest.raises(ValueError, match="hit_level"):
        compare_runs(document, chunk)
    assert compare_runs(document, chunk, allow_incompatible=True)["compatibility_overridden"]


# ------------------------------------------------------------- through the CLI
@pytest.fixture
def server():
    srv = make_server()
    serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def cli(*args):
    result = runner.invoke(app, [str(a) for a in args])
    return result, json.loads(result.stdout[result.stdout.find("{") :])


def test_predict_writes_a_failures_file_and_exits_non_zero_by_default(tmp_path):
    srv = make_server(fail_first=1)  # exactly one question fails
    serve_in_thread(srv)
    try:
        port = srv.server_address[1]
        cfg = tmp_path / "adapter.json"
        cfg.write_text(json.dumps({"base_url": f"http://127.0.0.1:{port}", "max_retries": 0}))
        dataset = tmp_path / "dev.jsonl"
        dataset.write_text(
            "".join(c.model_dump_json() + "\n" for c in demo_cases()), encoding="utf-8"
        )
        args = ["predict", dataset, "--adapter", "generic", "--adapter-config", cfg,
                "--target-revision", "rev"]  # fmt: skip
        strict, out = cli(*args, "--output", tmp_path / "a.jsonl")
        assert strict.exit_code == 1 and out["status"] == "completed_with_failures"
    finally:
        srv.shutdown()
        srv.server_close()
    saved = json.loads((tmp_path / "a.failures.json").read_text(encoding="utf-8"))
    assert saved["attempted"] == 3 and len(saved["failed"]) == 1
    assert saved["failed"][0]["kind"] == "error" and saved["failed"][0]["latency_ms"] >= 0
    assert sum(1 for _ in (tmp_path / "a.jsonl").open(encoding="utf-8")) == 2


def test_allow_failures_exits_zero_but_still_counts_them(tmp_path):
    srv = make_server(fail_first=1)
    serve_in_thread(srv)
    try:
        port = srv.server_address[1]
        cfg = tmp_path / "adapter.json"
        cfg.write_text(json.dumps({"base_url": f"http://127.0.0.1:{port}", "max_retries": 0}))
        dataset = tmp_path / "dev.jsonl"
        dataset.write_text(
            "".join(c.model_dump_json() + "\n" for c in demo_cases()), encoding="utf-8"
        )
        result, out = cli(
            "predict", dataset, "--adapter", "generic", "--adapter-config", cfg,
            "--target-revision", "rev", "--output", tmp_path / "b.jsonl", "--allow-failures",
        )  # fmt: skip
    finally:
        srv.shutdown()
        srv.server_close()
    assert result.exit_code == 0 and len(out["failed"]) == 1
    assert out["failures_file"].endswith("b.failures.json")


def test_evaluate_reports_operational_checks_and_ceilings(tmp_path):
    preds = tmp_path / "preds.jsonl"
    write_jsonl(
        preds,
        [
            rec(f"q-{i}", latency_ms=500.0 * i, input_tokens=1000, output_tokens=200)
            for i in range(1, 5)
        ],
    )
    failures = tmp_path / "preds.failures.json"
    failures.write_text(json.dumps({"attempted": 5, "failed": [{"kind": "timeout"}]}))
    pricing = tmp_path / "pricing.json"
    pricing.write_text(json.dumps({
        "input_usd_per_million": "0.5", "output_usd_per_million": "2.0",
        "source_url": "https://example.test/prices", "checked_on": "2026-11-22",
    }))  # fmt: skip
    thresholds = tmp_path / "thresholds.yaml"
    thresholds.write_text(
        "ceilings:\n  latency_p95_ms: 1500\n  error_rate: 0.1\n  cost_per_query_usd: 0.01\n",
        encoding="utf-8",
    )
    result, run = cli(
        "evaluate", preds, "--output", tmp_path / "run.json", "--target-revision", "rev",
        "--dataset-hash", HASH, "--corpus-hash", HASH, "--retrieval-mode", "lexical",
        "--allow-unverified-target", "--failures", failures, "--pricing", pricing,
        "--thresholds", thresholds,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    obs = run["observability"]
    assert obs["latency_ms"]["p95"] == 2000 and obs["error_rate"]["rate"] == 0.2
    assert float(obs["cost"]["per_query_usd"]) == pytest.approx(0.0009)
    by_name = {c["ceiling"]: c["result"] for c in run["ceiling_check"]["checks"]}
    assert by_name == {"latency_p95_ms": "FAIL", "error_rate": "FAIL", "cost_per_query_usd": "PASS"}
    assert run["ceiling_check"]["overall"] == "failed"

    text = runner.invoke(app, ["report", str(tmp_path / "run.json")]).stdout
    assert "## Operational checks" in text and "p95 2000.0 ms" in text
    assert "## Ceilings" in text and "| latency_p95_ms | 1500 | 2000 | FAIL |" in text
    assert "Hit@k level: `document`" in text


def test_evaluate_rejects_bad_option_files_before_doing_anything(tmp_path):
    preds = tmp_path / "preds.jsonl"
    write_jsonl(preds, [rec()])
    bad = tmp_path / "bad.yaml"
    bad.write_text("ceilings:\n  nope: 1\n", encoding="utf-8")
    result, out = cli(
        "evaluate", preds, "--output", tmp_path / "run.json", "--target-revision", "rev",
        "--dataset-hash", HASH, "--corpus-hash", HASH, "--retrieval-mode", "lexical",
        "--allow-unverified-target", "--thresholds", bad,
    )  # fmt: skip
    assert result.exit_code == 2 and out["status"] == "blocked" and "nope" in out["reason"]
    assert not (tmp_path / "run.json").exists()
