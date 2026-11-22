"""``ragkit init``: starter files, and an optional, explicitly confirmed copy of the agent skill.

Nothing is overwritten and nothing is copied into an agent's skills folder unless the person
says yes (or passes --skill-dir, which is the same consent given up front).
"""

import shutil
from importlib import resources
from pathlib import Path

CONFIG_TEMPLATE = """\
# ragkit.yaml: settings for `ragkit run`. Paths are relative to this file.
target:
  adapter: generic        # generic (any app with a JSON HTTP endpoint) or builder
  config: adapter.json    # how to talk to your app (test: ragkit adapter test)
  repo: ../my-rag-app     # local git checkout of the system under test; no uncommitted changes
corpus: docs              # your documents plus provenance.json (ragkit corpus init)
dataset: frozen           # the frozen golden set; a person makes it (import, review, freeze)
output: ragkit-out        # predictions, run files and reports are written here
# revision: <sha>         # optional: a specific commit of target.repo (default: its HEAD)
"""

ADAPTER_TEMPLATE = """\
{
  "base_url": "http://localhost:3000",
  "endpoint": "/api/chat",
  "question_field": "question",
  "answer_path": "answer",
  "contexts_path": "retrieved_contexts",
  "source_ids_path": "retrieved_source_ids",
  "retrieval_mode_path": "retrieval_mode",
  "headers": {},
  "max_retries": 2
}
"""

SKILL_NAME = "rag-eval-kit"
DEFAULT_SKILL_PARENT = ".claude/skills"


class InitError(ValueError):
    pass


def _write_new(path: Path, text: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError:
        raise InitError(f"{path.name} already exists; init never overwrites") from None


def write_starter_files(directory: Path) -> list[str]:
    """Write ragkit.yaml and adapter.json. Refuses if either exists, and writes neither then."""
    config, adapter = directory / "ragkit.yaml", directory / "adapter.json"
    for path in (config, adapter):
        if path.exists():
            raise InitError(f"{path.name} already exists; init never overwrites")
    directory.mkdir(parents=True, exist_ok=True)
    _write_new(config, CONFIG_TEMPLATE)
    _write_new(adapter, ADAPTER_TEMPLATE)
    return [config.name, adapter.name]


def skill_source() -> Path:
    """The skill folder: packaged with the wheel, or the repository's skill/ in a clone."""
    packaged = resources.files("rag_eval_kit").joinpath("skill_data")
    if packaged.is_dir():
        return Path(str(packaged))
    clone = Path(__file__).resolve().parents[2] / "skill"
    if (clone / "SKILL.md").is_file():
        return clone
    raise InitError("The skill files were not found in this installation")


def copy_skill(skills_parent: Path) -> Path:
    """Copy the skill to <skills_parent>/rag-eval-kit. Never overwrites an existing folder."""
    source = skill_source()
    destination = skills_parent / SKILL_NAME
    if destination.exists():
        raise InitError(f"{destination} already exists; the skill was not copied")
    skills_parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination
