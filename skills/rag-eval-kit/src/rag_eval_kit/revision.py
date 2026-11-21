"""Read-only target revision verification for reproducible future runs."""

import re
import subprocess
from pathlib import Path


class RevisionError(RuntimeError):
    pass


def verify_revision(path: Path, revision: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", revision):
        raise RevisionError("Use an explicit tag, branch or SHA without revision expressions")

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode:
            raise RevisionError("Git revision verification failed; check the path and revision")
        return result.stdout.strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != path.resolve():
        raise RevisionError("Builder path must be the repository root")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise RevisionError("Target working tree is dirty; benchmarking is refused")
    target = git("rev-parse", "--verify", f"{revision}^{{commit}}")
    head = git("rev-parse", "HEAD")
    if target != head:
        raise RevisionError("Target HEAD does not match the requested revision")
    return {"requested_revision": revision, "commit": target, "working_tree": "clean"}
