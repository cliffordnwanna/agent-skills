import csv
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from rag_eval_kit.adapters.base import AdapterError
from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig
from rag_eval_kit.cli import app
from rag_eval_kit.corpus import load_corpus
from rag_eval_kit.dataset import build_candidates
from rag_eval_kit.freeze import ReviewError, load_review, split_cases
from rag_eval_kit.mock_server import demo_cases, make_server, serve_in_thread
from rag_eval_kit.predict import run_predictions

runner = CliRunner()
BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "fastapi-docs"


def _start(**kwargs):
    srv = make_server(**kwargs)
    serve_in_thread(srv)
    return srv


def _stop(srv):
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def server():
    srv = _start()
    yield srv
    _stop(srv)


def _config(srv, **extra):
    return GenericHTTPConfig(
        base_url=f"http://127.0.0.1:{srv.server_address[1]}", retry_backoff_seconds=0, **extra
    )


def test_generic_adapter_against_real_local_server(server):
    with GenericHTTPAdapter(_config(server)) as adapter:
        records, failures = run_predictions(
            demo_cases(), lambda c: adapter.predict(c, "rev"), concurrency=3
        )
    assert not failures and len(records) == 3
    assert {r.retrieval_mode for r in records} == {"lexical"}
    assert records[0].retrieved_source_ids == ["alpha"]


def test_generic_adapter_retries_transient_503_then_succeeds():
    srv = _start(fail_first=2)
    try:
        with GenericHTTPAdapter(_config(srv, max_retries=2)) as adapter:
            record = adapter.predict(demo_cases()[0], "rev")
        assert record.retrieved_source_ids == ["alpha"]
    finally:
        _stop(srv)


def test_generic_adapter_retries_are_bounded():
    srv = _start(fail_first=10)
    try:
        with GenericHTTPAdapter(_config(srv, max_retries=1)) as adapter:
            with pytest.raises(AdapterError, match="503"):
                adapter.predict(demo_cases()[0], "rev")
    finally:
        _stop(srv)


def test_connection_failure_is_reported_not_dropped():
    config = GenericHTTPConfig(base_url="http://127.0.0.1:9", max_retries=0)
    with GenericHTTPAdapter(config, httpx.Client(timeout=2)) as adapter:
        records, failures = run_predictions(demo_cases(), lambda c: adapter.predict(c, "rev"))
    assert records == [] and len(failures) == 3
    assert failures[0]["question_id"] == "demo-01"


def test_smoke_command_is_offline_and_passes():
    result = runner.invoke(app, ["smoke"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["status"] == "smoke_passed" and out["paid_calls"] == 0


def test_corpus_inspect_verifies_hashes():
    result = runner.invoke(app, ["corpus", "inspect", str(BENCH)])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["builder_limits_ok"] and len(out["documents"]) == 6


def _sheet(tmp_path, keep):
    generated = tmp_path / "gen"
    result = runner.invoke(
        app, ["dataset", "generate", "--corpus-dir", str(BENCH), "--output-dir", str(generated)]
    )
    assert result.exit_code == 0
    with (generated / "review.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for i, row in enumerate(rows):
        row["keep"] = keep(i, row)
    path = tmp_path / "review.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_review_rejects_undecided_rows(tmp_path):
    sheet = _sheet(tmp_path, lambda i, r: "yes" if i else "")
    _, docs, _ = load_corpus(BENCH)
    with pytest.raises(ReviewError, match="no keep"):
        load_review(sheet, docs)
    result = runner.invoke(app, ["dataset", "review", str(sheet), "--corpus-dir", str(BENCH)])
    assert result.exit_code == 2


def _freeze_args(sheet, seed="7"):
    return [
        "dataset",
        "freeze",
        str(sheet),
        "--corpus-dir",
        str(BENCH),
        "--approved-by",
        "tester",
        "--seed",
        seed,
    ]


def test_freeze_is_deterministic_leak_free_and_never_overwrites(tmp_path):
    sheet = _sheet(tmp_path, lambda i, r: "yes")
    a = runner.invoke(app, [*_freeze_args(sheet), "--output-dir", str(tmp_path / "a")])
    b = runner.invoke(app, [*_freeze_args(sheet), "--output-dir", str(tmp_path / "b")])
    assert a.exit_code == 0 and b.exit_code == 0
    ma, mb = json.loads(a.stdout), json.loads(b.stdout)
    for key in ("golden_sha256", "dev_sha256", "heldout_sha256"):
        assert ma[key] == mb[key]
    assert ma["counts"]["golden"] == 60
    dev = {json.loads(x)["question_id"] for x in (tmp_path / "a" / "dev.jsonl").open()}
    held = {json.loads(x)["question_id"] for x in (tmp_path / "a" / "heldout.jsonl").open()}
    assert not dev & held and len(dev | held) == 60
    spans = {c.question_id: set(c.reference_evidence) for c in build_candidates()}
    for d in dev:
        for h in held:
            assert not (spans[d] & spans[h])
    again = runner.invoke(app, [*_freeze_args(sheet), "--output-dir", str(tmp_path / "a")])
    assert again.exit_code == 2


def test_freeze_requires_named_reviewer(tmp_path):
    sheet = _sheet(tmp_path, lambda i, r: "yes")
    args = _freeze_args(sheet)
    args[args.index("tester")] = " "
    result = runner.invoke(app, [*args, "--output-dir", str(tmp_path / "x")])
    assert result.exit_code == 2 and not (tmp_path / "x").exists()


def test_split_is_stratified_by_category():
    dev, held = split_cases(build_candidates(), seed=1)
    assert 20 <= len(held) <= 28
    assert len({c.category for c in held}) == 5


def test_predict_command_writes_predictions_and_reports_failures(tmp_path, server):
    dataset = tmp_path / "d.jsonl"
    dataset.write_text("".join(c.model_dump_json() + "\n" for c in demo_cases()), encoding="utf-8")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"base_url": f"http://127.0.0.1:{server.server_address[1]}"}))
    out = tmp_path / "p.jsonl"
    base = ["predict", str(dataset), "--adapter", "generic", "--target-revision", "rev"]
    ok = runner.invoke(app, [*base, "--adapter-config", str(cfg), "--output", str(out)])
    assert ok.exit_code == 0, ok.output
    assert len(out.read_text().splitlines()) == 3
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"base_url": "http://127.0.0.1:9", "max_retries": 0}))
    failed = runner.invoke(
        app, [*base, "--adapter-config", str(bad), "--output", str(tmp_path / "q.jsonl")]
    )
    assert failed.exit_code == 1
    assert json.loads(failed.stdout)["status"] == "completed_with_failures"
