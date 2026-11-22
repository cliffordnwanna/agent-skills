"""Readable output by default, exact JSON with --json. Exit codes never depend on the mode."""

import json
import os
import subprocess
import sys

import pytest
from test_pipeline import Project, project  # noqa: F401  (reuse the throwaway-project fixture)
from typer.testing import CliRunner

from rag_eval_kit import output
from rag_eval_kit.adapters.files import write_jsonl
from rag_eval_kit.cli import app
from rag_eval_kit.mock_server import demo_cases, make_server, serve_in_thread
from rag_eval_kit.models import EvaluationRecord

runner = CliRunner()
HUMAN = {"RAGKIT_OUTPUT": "human"}
HASH = "a" * 64


def human(*args, **kwargs):
    return runner.invoke(app, [str(a) for a in args], env=HUMAN, **kwargs)


def assert_readable(text):
    assert "{" not in text and '"status"' not in text  # not JSON
    assert text.strip()


# ---------------------------------------------------------------- the switch
def test_smoke_is_readable_by_default_and_json_on_request():
    result = human("smoke")
    assert result.exit_code == 0
    assert_readable(result.stdout)
    assert "✓ Smoke test passed" in result.stdout and "Paid calls: 0" in result.stdout
    assert "Next: run `ragkit init`" in result.stdout

    as_json = runner.invoke(app, ["--json", "smoke"])
    assert json.loads(as_json.stdout)["status"] == "smoke_passed"
    os.environ["RAGKIT_OUTPUT"] = (
        "json"  # the flag leaves the process in JSON mode; keep it that way
    )


def _run_module(*args, env=None):
    full_env = {**os.environ, "RAGKIT_OUTPUT": "", **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "rag_eval_kit.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=full_env,
        check=False,
    )


def test_the_real_entry_point_accepts_json_anywhere_on_the_line():
    plain = _run_module("smoke")
    assert plain.returncode == 0 and "Smoke test passed" in plain.stdout
    assert "{" not in plain.stdout
    for args in (["smoke", "--json"], ["--json", "smoke"]):
        flagged = _run_module(*args)
        assert flagged.returncode == 0
        assert json.loads(flagged.stdout)["status"] == "smoke_passed"


def test_plain_ascii_marks_when_the_terminal_cannot_show_checkmarks():
    result = _run_module("smoke", env={"PYTHONIOENCODING": "ascii", "NO_COLOR": "1"})
    assert result.returncode == 0, result.stderr
    assert "[ok] Smoke test passed" in result.stdout
    assert result.stdout.isascii()


def test_marks_fall_back_without_unicode(monkeypatch):
    monkeypatch.setattr(output, "_unicode_ok", lambda: False)
    assert output._marks()["ok"] == "[ok]" and output._marks()["bad"] == "[x]"


# ----------------------------------------------------------- setup commands
def test_init_lists_what_it_wrote_and_numbers_the_next_steps(tmp_path):
    result = human("init", "--directory", tmp_path / "p", "--no-skill")
    assert result.exit_code == 0
    assert_readable(result.stdout)
    assert "ragkit.yaml and adapter.json" in result.stdout
    assert "Agent skill not copied" in result.stdout
    assert "\n  1. Edit adapter.json" in result.stdout and "\n  4. " in result.stdout


def test_init_refusal_is_readable_and_keeps_the_exit_code(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "ragkit.yaml").write_text("x: 1\n", encoding="utf-8")
    result = human("init", "--directory", tmp_path / "p", "--no-skill")
    assert result.exit_code == 2
    assert "Stopped" in result.stdout and "never overwrites" in result.stdout


def test_dataset_steps_say_who_must_approve(project):  # noqa: F811
    cand = project.root / "cand"
    questions = project.root / "q.jsonl"
    questions.write_text(
        "".join(json.dumps(c.model_dump(mode="json")) + "\n" for c in demo_cases()),
        encoding="utf-8",
    )
    imported = human(
        "dataset", "import", questions, "--corpus-dir", project.corpus, "--output-dir", cand
    )
    assert imported.exit_code == 0 and "Imported 3 questions" in imported.stdout
    assert "NOT approved" in imported.stdout and "write yes or no" in imported.stdout

    sheet = cand / "review.csv"
    import csv

    rows = list(csv.DictReader(sheet.open(encoding="utf-8", newline="")))
    for row in rows:
        row["keep"] = "yes"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    review = human("dataset", "review", sheet, "--corpus-dir", project.corpus)
    assert "Review sheet is valid" in review.stdout and "kept 3" in review.stdout
    frozen = human(
        "dataset", "freeze", sheet, "--corpus-dir", project.corpus,
        "--output-dir", project.dataset, "--approved-by", "Reviewer",
    )  # fmt: skip
    assert "Question set frozen" in frozen.stdout and "approved by Reviewer" in frozen.stdout
    assert "held-out" in frozen.stdout and "use once" in frozen.stdout


# --------------------------------------------------------------- adapter test
@pytest.fixture
def server():
    srv = make_server()
    serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def adapter_config(tmp_path, server, **extra):
    path = tmp_path / "adapter.json"
    body = {"base_url": f"http://127.0.0.1:{server.server_address[1]}", **extra}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_adapter_test_success_reads_naturally(tmp_path, server):
    cfg = adapter_config(tmp_path, server)
    result = human(
        "adapter",
        "test",
        "--adapter-config",
        cfg,
        "--question",
        "Which port does the alpha service use?",
    )
    assert result.exit_code == 0
    assert_readable(result.stdout)
    assert "✓ Your app answered" in result.stdout and "Passages found: 1" in result.stdout
    assert "Nothing was saved" in result.stdout


def test_adapter_test_failure_names_the_keys_to_fix(tmp_path, server):
    cfg = adapter_config(tmp_path, server, answer_path="data.text")
    result = human("adapter", "test", "--adapter-config", cfg)
    assert result.exit_code == 2
    assert "✗ Could not read your app's answer" in result.stdout
    assert "top-level keys" in result.stdout and "answer" in result.stdout
    assert "Next:" in result.stdout


# -------------------------------------------------------------------- ragkit run
def test_run_summary_shows_each_step_and_resumes_clearly(project):  # noqa: F811
    project.freeze_dataset()
    waiting = human("run", "--config", project.yaml, "--dry-run")
    assert "Dry run: nothing was changed" in waiting.stdout and "ragkit predict" in waiting.stdout

    first = human("run", "--config", project.yaml)
    assert first.exit_code == 0, first.stdout
    assert_readable(first.stdout)
    assert "✓ ragkit run finished" in first.stdout and "0 paid calls" in first.stdout
    assert "✓ documents" in first.stdout and "3 documents verified" in first.stdout
    assert "✓ ask your app" in first.stdout and "✓ score answers" in first.stdout

    again = human("run", "--config", project.yaml)
    assert again.stdout.count("already done, skipped") == 3


def test_run_waits_for_a_person_with_numbered_steps(project):  # noqa: F811
    result = human("run", "--config", project.yaml)
    assert result.exit_code == 0
    assert "Waiting for a person" in result.stdout
    assert "freeze" in result.stdout and "Then run `ragkit run` again" in result.stdout


def test_run_refusals_explain_themselves_and_keep_exit_code_2(project):  # noqa: F811
    project.freeze_dataset()
    (project.target / "app.py").write_text("uncommitted\n", encoding="utf-8")
    result = human("run", "--config", project.yaml)
    assert result.exit_code == 2
    assert "✗ ragkit run stopped" in result.stdout and "dirty" in result.stdout
    assert_readable(result.stdout)


# ------------------------------------------------------- predict and evaluate
def test_predict_reports_answered_and_failed(tmp_path):
    srv = make_server(fail_first=1)
    serve_in_thread(srv)
    try:
        cfg = adapter_config(tmp_path, srv, max_retries=0)
        dataset = tmp_path / "dev.jsonl"
        dataset.write_text(
            "".join(c.model_dump_json() + "\n" for c in demo_cases()), encoding="utf-8"
        )
        result = human(
            "predict", dataset, "--adapter", "generic", "--adapter-config", cfg,
            "--target-revision", "rev", "--output", tmp_path / "p.jsonl",
        )  # fmt: skip
    finally:
        srv.shutdown()
        srv.server_close()
    assert result.exit_code == 1
    assert "2 answered, 1 failed" in result.stdout and "✗ demo-01" in result.stdout
    assert "--allow-failures" in result.stdout


def _records():
    return [
        EvaluationRecord(
            question_id=f"q-{i}", question="q?", answer="a", retrieved_source_ids=["alpha"],
            expected_source_ids=["alpha"], category="direct", target_revision="rev",
            retrieval_mode="lexical", latency_ms=100.0 * i,
        )
        for i in range(1, 5)
    ]  # fmt: skip


def test_evaluate_summary_shows_scores_speed_errors_and_ceilings(tmp_path):
    preds = tmp_path / "preds.jsonl"
    write_jsonl(preds, _records())
    failures = tmp_path / "preds.failures.json"
    failures.write_text(json.dumps({"attempted": 4, "failed": []}))
    thresholds = tmp_path / "t.yaml"
    thresholds.write_text("ceilings:\n  latency_p95_ms: 300\n  error_rate: 0.1\n", encoding="utf-8")
    result = human(
        "evaluate", preds, "--output", tmp_path / "run.json", "--target-revision", "rev",
        "--dataset-hash", HASH, "--corpus-hash", HASH, "--retrieval-mode", "lexical",
        "--allow-unverified-target", "--failures", failures, "--thresholds", thresholds,
    )  # fmt: skip
    assert result.exit_code == 0, result.stdout
    assert_readable(result.stdout)
    text = result.stdout
    assert "✓ Evaluation complete (lexical, free)" in text
    assert "hit@1 1.00" in text and "document-level" in text
    assert "median 200 ms, slow end 400 ms" in text
    assert "Errors: 0.0% of questions" in text
    assert "✗ Ceilings: failed" in text and "latency_p95_ms: 400 (limit 300) FAIL" in text
    assert "Saved:" in text and "ragkit report run.json" in text


# ----------------------------------------------------------------- robustness
@pytest.mark.parametrize("status", sorted(output.RENDERERS) + ["something_new", "", "completed"])
def test_every_renderer_survives_minimal_input(status):
    text = output.render({"status": status})
    assert isinstance(text, str) and text.strip()


@pytest.mark.parametrize(
    "value",
    [
        {"status": "completed", "stages": []},
        {"status": "blocked", "stages": [{"stage": "corpus", "state": "done"}], "reason": "x"},
        {"status": "waiting_for_human", "stages": []},
        {"status": "dry_run", "stages": [{"stage": "predict", "state": "would_run"}]},
        {"metric_deltas": {"hit_at_1": {"mean_delta": None}}},
        {"status": "completed", "predictions": 0, "failed": []},
        {"status": "completed", "metrics": {}, "retrieval_mode": "semantic"},
        {"planned_call_count": 3},
    ],
)
def test_odd_shapes_never_crash_the_renderer(value):
    assert output.render(value).strip()


def test_json_mode_prints_exactly_what_it_always_did(capsys):
    os.environ["RAGKIT_OUTPUT"] = "json"
    output.emit({"status": "frozen", "counts": {"golden": 3}})
    assert json.loads(capsys.readouterr().out) == {"status": "frozen", "counts": {"golden": 3}}


def test_long_paths_are_never_split_across_lines():
    long_path = "/very/long/folder/" + "x" * 120 + "/ragkit-out"
    text = output.render({"status": "blocked", "reason": f"The folder ({long_path}) is bad."})
    assert long_path in text  # one unbroken token, even though it is wider than the line
