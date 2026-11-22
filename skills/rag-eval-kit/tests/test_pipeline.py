"""ragkit run: gates, resume, refusals. Uses the local mock RAG server only; no paid calls."""

import csv
import json
import subprocess

import pytest
import yaml
from typer.testing import CliRunner

from rag_eval_kit.cli import app
from rag_eval_kit.mock_server import DEMO_DOCS, demo_cases, make_server, serve_in_thread

runner = CliRunner()


def _git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def _invoke(*args):
    result = runner.invoke(app, [str(a) for a in args])
    return result, (json.loads(result.stdout) if result.stdout.strip().startswith("{") else {})


def _read_sheet(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_sheet(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Project:
    """A throwaway project: corpus, target git repo, adapter config, ragkit.yaml."""

    def __init__(self, root, server):
        self.root = root
        self.corpus = root / "docs"
        self.target = root / "app"
        self.dataset = root / "frozen"
        self.out = root / "out"
        self.yaml = root / "ragkit.yaml"
        self.adapter = root / "adapter.json"
        self.server = server

    def build_inputs(self):
        self.corpus.mkdir()
        for source_id, text in DEMO_DOCS.items():
            (self.corpus / f"{source_id}.txt").write_text(text + "\n", encoding="utf-8")
        self.target.mkdir()
        (self.target / "app.py").write_text("print('v1')\n", encoding="utf-8")
        _git(self.target, "init")
        _git(self.target, "config", "user.name", "Test Fixture")
        _git(self.target, "config", "user.email", "fixture@example.test")
        _git(self.target, "add", ".")
        _git(self.target, "commit", "-m", "v1")
        port = self.server.server_address[1]
        self.adapter.write_text(
            json.dumps({"base_url": f"http://127.0.0.1:{port}", "max_retries": 0}),
            encoding="utf-8",
        )
        result, _ = _invoke(
            "corpus", "init", self.corpus, "--name", "Demo", "--license", "MIT",
            "--license-url", "internal", "--source-repository", "internal",
            "--source-revision", "c" * 40,
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        self.write_config()

    def write_config(self, **overrides):
        config = {
            "target": {"adapter": "generic", "config": "adapter.json", "repo": "app"},
            "corpus": "docs",
            "dataset": "frozen",
            "output": "out",
        }
        config.update(overrides)
        self.yaml.write_text(yaml.safe_dump(config), encoding="utf-8")

    def freeze_dataset(self):
        questions = self.root / "questions.jsonl"
        questions.write_text(
            "".join(json.dumps(c.model_dump(mode="json")) + "\n" for c in demo_cases()),
            encoding="utf-8",
        )
        cand = self.root / "cand"
        result, _ = _invoke(
            "dataset", "import", questions, "--corpus-dir", self.corpus, "--output-dir", cand
        )
        assert result.exit_code == 0, result.output
        sheet = cand / "review.csv"
        rows = _read_sheet(sheet)
        for row in rows:
            row["keep"] = "yes"
        _write_sheet(sheet, rows)
        result, _ = _invoke(
            "dataset", "freeze", sheet, "--corpus-dir", self.corpus,
            "--output-dir", self.dataset, "--approved-by", "Reviewer",
        )  # fmt: skip
        assert result.exit_code == 0, result.output

    def run(self, *extra):
        return _invoke("run", "--config", self.yaml, *extra)


@pytest.fixture
def project(tmp_path):
    server = make_server()
    serve_in_thread(server)
    proj = Project(tmp_path, server)
    proj.build_inputs()
    yield proj
    server.shutdown()
    server.server_close()


def test_waits_for_a_human_when_nothing_is_frozen(project):
    result, out = project.run()
    assert result.exit_code == 0
    assert out["status"] == "waiting_for_human" and out["gate"] == "golden_set_review"
    assert any("dataset freeze" in line for line in out["what_to_do"])
    assert not project.out.exists()  # nothing was predicted or written


def test_dry_run_shows_commands_and_changes_nothing(project):
    project.freeze_dataset()
    result, out = project.run("--dry-run")
    assert result.exit_code == 0 and out["status"] == "dry_run"
    commands = [s["command"] for s in out["stages"] if "command" in s]
    assert commands[0].startswith("ragkit predict") and commands[1].startswith("ragkit evaluate")
    assert not project.out.exists()


def test_full_run_then_resume_skips_finished_steps(project):
    project.freeze_dataset()
    first_result, first = project.run()
    assert first_result.exit_code == 0, first_result.output
    assert first["status"] == "completed" and first["paid_calls"] == 0
    states = {s["stage"]: s["state"] for s in first["stages"]}
    assert states["predict"] == states["evaluate"] == states["report"] == "done"

    run = json.loads((project.out / "dev" / "run-lexical.json").read_text(encoding="utf-8"))
    head = subprocess.run(
        ["git", "-C", str(project.target), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert run["target_revision"] == head and run["retrieval_mode"] == "lexical"
    assert run["evaluator_revision"]["commit"]  # the evaluator's own commit is recorded
    assert (project.out / "dev" / "report.md").read_text(encoding="utf-8").strip()

    again_result, again = project.run()
    assert again_result.exit_code == 0 and again["status"] == "completed"
    assert {
        s["state"] for s in again["stages"] if s["stage"] in {"predict", "evaluate", "report"}
    } == {"skipped_already_done"}


def test_heldout_needs_explicit_confirmation(project):
    project.freeze_dataset()
    result, out = project.run("--split", "heldout")
    assert result.exit_code == 2 and "one final run" in out["reason"]
    assert not project.out.exists()
    confirmed, done = project.run("--split", "heldout", "--confirm-heldout")
    assert confirmed.exit_code == 0, confirmed.output
    assert done["status"] == "completed" and done["split"] == "heldout"


def test_refuses_a_dirty_target(project):
    project.freeze_dataset()
    (project.target / "app.py").write_text("print('uncommitted')\n", encoding="utf-8")
    result, out = project.run()
    assert result.exit_code == 2 and "dirty" in out["reason"]
    assert not project.out.exists()


def test_refuses_without_a_verifiable_target(project):
    project.freeze_dataset()
    project.write_config(target={"adapter": "generic", "config": "adapter.json"})
    result, out = project.run()
    assert result.exit_code == 2 and "target.repo" in out["reason"]


def test_unverified_target_needs_two_explicit_settings(project):
    project.freeze_dataset()
    project.write_config(
        target={"adapter": "generic", "config": "adapter.json", "allow_unverified_target": True},
        revision="release-1",
    )
    result, out = project.run()
    assert result.exit_code == 0, result.output
    assert out["status"] == "completed"
    assert [s for s in out["stages"] if s["stage"] == "revision"][0][
        "target_revision"
    ] == "release-1"


def test_unknown_setting_is_rejected(project):
    project.write_config(typo_key=1)
    result, out = project.run()
    assert result.exit_code == 2 and "typo_key" in out["reason"]


def test_changed_dataset_is_refused(project):
    project.freeze_dataset()
    dev = project.dataset / "dev.jsonl"
    dev.write_text(dev.read_text(encoding="utf-8").replace("alpha", "ALPHA", 1), encoding="utf-8")
    result, out = project.run()
    assert result.exit_code == 2 and "changed since it was frozen" in out["reason"]


def test_changed_corpus_is_refused(project):
    project.freeze_dataset()
    (project.corpus / "alpha.txt").write_text("changed\n", encoding="utf-8")
    result, out = project.run()
    assert result.exit_code == 2 and "hash mismatch" in out["reason"].lower()


def test_predictions_for_another_revision_are_not_reused(project):
    project.freeze_dataset()
    assert project.run()[0].exit_code == 0
    (project.target / "app.py").write_text("print('v2')\n", encoding="utf-8")
    _git(project.target, "commit", "-am", "v2")
    result, out = project.run()
    assert result.exit_code == 2 and "different revision" in out["reason"]


def test_target_failures_are_reported_and_never_resumed_from(project):
    project.freeze_dataset()
    failing = make_server(fail_first=100)
    serve_in_thread(failing)
    try:
        port = failing.server_address[1]
        project.adapter.write_text(
            json.dumps({"base_url": f"http://127.0.0.1:{port}", "max_retries": 0}),
            encoding="utf-8",
        )
        result, out = project.run()
    finally:
        failing.shutdown()
        failing.server_close()
    assert result.exit_code == 2 and out["failed_stage"] == "predict"
    assert not (project.out / "dev" / "predictions.jsonl").exists()  # no half-finished file


def test_output_inside_the_target_repo_must_be_git_ignored(project):
    project.freeze_dataset()
    project.write_config(output="app/ragkit-out")  # inside the target repository
    blocked, out = project.run()
    assert blocked.exit_code == 2 and ".gitignore" in out["reason"]
    assert not (project.target / "ragkit-out").exists()  # nothing was written before refusing

    (project.target / ".gitignore").write_text("ragkit-out/\n", encoding="utf-8")
    _git(project.target, "add", ".gitignore")
    _git(project.target, "commit", "-m", "ignore ragkit output")
    done, summary = project.run()
    assert done.exit_code == 0, done.output
    assert summary["status"] == "completed"
    assert (project.target / "ragkit-out" / "dev" / "run-lexical.json").exists()
