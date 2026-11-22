"""Which version of the evaluator produced a run.

Scoring code must not change between a baseline run and the run it is compared with. Every
run records the evaluator's own commit so a mismatch can be seen afterwards. This is metadata
only: it is not used for scoring, comparison or any decision.
"""

import json
import re
import subprocess
from functools import lru_cache
from importlib import metadata
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}")


def _from_direct_url(text: str | None) -> dict[str, str] | None:
    """Commit of a ``pip install git+...`` or ``uv tool install git+...`` (PEP 610)."""
    if not text:
        return None
    try:
        vcs = json.loads(text).get("vcs_info") or {}
    except ValueError:
        return None
    commit = vcs.get("commit_id")
    if isinstance(commit, str) and _SHA.fullmatch(commit):
        return {"commit": commit, "source": "git-install", "working_tree": "not-applicable"}
    return None


def _git(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _from_checkout(package_dir: Path) -> dict[str, str] | None:
    """Commit of a source checkout. ``dirty`` means uncommitted changes in the package code."""
    head = _git(package_dir, "rev-parse", "HEAD")
    if head is None or not _SHA.fullmatch(head):
        return None
    changes = _git(package_dir, "status", "--porcelain", "--untracked-files=all", "--", ".")
    state = "unknown" if changes is None else ("dirty" if changes else "clean")
    return {"commit": head, "source": "git-checkout", "working_tree": state}


@lru_cache(maxsize=1)
def evaluator_revision() -> dict[str, str]:
    """Best-effort commit of this evaluator. Never raises."""
    try:
        found = _from_direct_url(metadata.distribution("rag-eval-kit").read_text("direct_url.json"))
    except metadata.PackageNotFoundError:
        found = None
    if found is None:
        found = _from_checkout(Path(__file__).resolve().parent)
    return found or {"commit": "unknown", "source": "not-a-git-checkout", "working_tree": "unknown"}
