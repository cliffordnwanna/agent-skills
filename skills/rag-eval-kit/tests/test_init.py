"""ragkit init: starter files never overwrite; the skill is copied only with explicit consent."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_eval_kit.adapters.generic_http import GenericHTTPConfig
from rag_eval_kit.cli import app
from rag_eval_kit.pipeline import load_config
from rag_eval_kit.scaffold import skill_source

runner = CliRunner()


def init(tmp_path, *args, **kwargs):
    result = runner.invoke(app, ["init", "--directory", str(tmp_path / "proj"), *args], **kwargs)
    # The test runner echoes typed answers into stdout, so read the JSON from its first brace.
    start = result.stdout.find("{")
    return result, (json.loads(result.stdout[start:]) if start >= 0 else {})


def test_writes_valid_starter_files(tmp_path):
    result, out = init(tmp_path, "--no-skill")
    assert result.exit_code == 0, result.output
    assert out["status"] == "initialised" and out["skill"] == {"copied": False}
    proj = tmp_path / "proj"
    config, _ = load_config(proj / "ragkit.yaml")  # the template is a valid settings file
    assert config.target.adapter == "generic" and config.output.name == "ragkit-out"
    GenericHTTPConfig(**json.loads((proj / "adapter.json").read_text(encoding="utf-8")))


def test_never_overwrites_and_writes_nothing_if_one_file_exists(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "ragkit.yaml").write_text("mine: true\n", encoding="utf-8")
    result, out = init(tmp_path, "--no-skill")
    assert result.exit_code == 2 and "never overwrites" in out["reason"]
    assert (proj / "ragkit.yaml").read_text(encoding="utf-8") == "mine: true\n"
    assert not (proj / "adapter.json").exists()


def test_skill_is_not_copied_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result, out = init(tmp_path, input="n\n")
    assert result.exit_code == 0 and out["skill"] == {"copied": False}
    assert not (tmp_path / ".claude").exists()


def test_no_answer_is_a_no(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result, out = init(tmp_path, input="")  # nobody is there to answer
    assert result.exit_code == 0 and out["skill"] == {"copied": False}
    assert not (tmp_path / ".claude").exists()


def test_no_skill_flag_does_not_even_ask(tmp_path):
    result, _ = init(tmp_path, "--no-skill", input="y\n")
    assert "skill" not in result.stderr.lower()


def test_skill_is_copied_after_a_yes_and_a_folder(tmp_path):
    target = tmp_path / "agent-skills-folder"
    result, out = init(tmp_path, input=f"y\n{target}\n")
    assert result.exit_code == 0, result.output
    copied = Path(out["skill"]["path"])
    assert copied == target / "rag-eval-kit" and out["skill"]["copied"] is True
    assert (copied / "SKILL.md").is_file() and (copied / "references" / "disclosures.md").is_file()
    assert (copied / "SKILL.md").read_bytes() == (skill_source() / "SKILL.md").read_bytes()
    assert not (copied / "tests").exists()  # only the skill, not the source tree


def test_skill_dir_flag_is_explicit_consent(tmp_path):
    target = tmp_path / "skills"
    result, out = init(tmp_path, "--skill-dir", str(target))
    assert result.exit_code == 0, result.output
    assert (target / "rag-eval-kit" / "SKILL.md").is_file()
    assert out["skill"]["copied"] is True


def test_existing_skill_folder_is_never_overwritten(tmp_path):
    target = tmp_path / "skills"
    (target / "rag-eval-kit").mkdir(parents=True)
    (target / "rag-eval-kit" / "SKILL.md").write_text("my edited copy", encoding="utf-8")
    result, out = init(tmp_path, "--skill-dir", str(target))
    assert result.exit_code == 2 and out["status"] == "init_partial"
    assert (target / "rag-eval-kit" / "SKILL.md").read_text(encoding="utf-8") == "my edited copy"


@pytest.mark.parametrize("name", ["SKILL.md"])
def test_skill_source_has_the_files_the_readme_promises(name):
    root = skill_source()
    assert (root / name).is_file()
    assert {p.name for p in (root / "references").glob("*.md")} >= {
        "disclosures.md",
        "golden-set-rubric.md",
        "threshold-guide.md",
    }
