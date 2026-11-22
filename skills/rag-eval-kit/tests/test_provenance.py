import json
import subprocess
import sys

from typer.testing import CliRunner

from rag_eval_kit import provenance
from rag_eval_kit.cli import app

SHA = "b" * 40


def test_direct_url_commit_is_read_for_git_installs():
    text = json.dumps(
        {"url": "https://example.test/x", "vcs_info": {"vcs": "git", "commit_id": SHA}}
    )
    assert provenance._from_direct_url(text) == {
        "commit": SHA,
        "source": "git-install",
        "working_tree": "not-applicable",
    }


def test_direct_url_without_vcs_or_with_garbage_is_ignored():
    editable = json.dumps({"url": "file:///x", "dir_info": {"editable": True}})
    assert provenance._from_direct_url(editable) is None
    assert provenance._from_direct_url("not json") is None
    assert provenance._from_direct_url(None) is None
    assert provenance._from_direct_url(json.dumps({"vcs_info": {"commit_id": "short"}})) is None


def _git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def test_checkout_commit_and_dirty_state(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.test")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "first")
    clean = provenance._from_checkout(pkg)
    assert clean["working_tree"] == "clean" and len(clean["commit"]) == 40
    (pkg / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert provenance._from_checkout(pkg)["working_tree"] == "dirty"


def test_outside_a_checkout_is_unknown_not_an_error(tmp_path):
    assert provenance._from_checkout(tmp_path) is None


def test_evaluator_revision_never_raises_and_has_a_commit_field():
    provenance.evaluator_revision.cache_clear()
    info = provenance.evaluator_revision()
    assert set(info) == {"commit", "source", "working_tree"} and info["commit"]


def test_every_run_records_the_evaluator_revision():
    result = CliRunner().invoke(app, ["smoke"])
    assert result.exit_code == 0, result.output
    run = json.loads(result.stdout)["result"]
    assert set(run["evaluator_revision"]) == {"commit", "source", "working_tree"}
    assert sys.version_info >= (3, 12)
