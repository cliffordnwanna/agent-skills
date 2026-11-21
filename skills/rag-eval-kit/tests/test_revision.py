import subprocess

import pytest

from rag_eval_kit.revision import RevisionError, verify_revision


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    (tmp_path / "fixture.txt").write_text("one", encoding="utf-8")
    git(tmp_path, "add", "--", "fixture.txt")
    git(tmp_path, "commit", "-m", "test fixture")
    git(tmp_path, "tag", "baseline-v0")
    return tmp_path


def test_clean_tagged_revision_is_verified_without_checkout(repository):
    result = verify_revision(repository, "baseline-v0")
    assert result["commit"] == git(repository, "rev-parse", "HEAD")
    assert result["working_tree"] == "clean"


def test_dirty_and_untracked_files_reject_evaluation(repository):
    (repository / "untracked.txt").write_text("pending", encoding="utf-8")
    with pytest.raises(RevisionError, match="dirty"):
        verify_revision(repository, "baseline-v0")


def test_wrong_revision_rejects_evaluation(repository):
    (repository / "fixture.txt").write_text("two", encoding="utf-8")
    git(repository, "add", "--", "fixture.txt")
    git(repository, "commit", "-m", "second fixture")
    with pytest.raises(RevisionError, match="does not match"):
        verify_revision(repository, "baseline-v0")


def test_revision_options_and_subdirectories_rejected(repository):
    with pytest.raises(RevisionError):
        verify_revision(repository, "--help")
    subdir = repository / "subdir"
    subdir.mkdir()
    with pytest.raises(RevisionError, match="repository root"):
        verify_revision(subdir, "baseline-v0")
