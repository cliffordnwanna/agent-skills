"""``ragkit run``: the offline (lexical) pipeline driven by ragkit.yaml.

This module adds no scoring logic. It checks files, then calls the same ``ragkit`` commands a
person would type (shown in the output), so a run is exactly reproducible by hand. It stops at
the steps a person must do (approve the golden set) and resumes from the files already written.
It never makes paid calls: semantic scoring stays a separate, explicitly approved command.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rag_eval_kit.corpus import CorpusError, load_corpus
from rag_eval_kit.revision import RevisionError, verify_revision

Split = Literal["dev", "heldout"]


class TargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: Literal["generic", "builder"]
    config: Path = Field(description="Adapter config JSON, relative to ragkit.yaml")
    repo: Path | None = Field(
        default=None, description="Local git checkout of the system under test; must be clean"
    )
    allow_unverified_target: bool = False


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: TargetConfig
    corpus: Path
    dataset: Path
    revision: str | None = Field(default=None, min_length=1, max_length=200)
    output: Path = Path("ragkit-out")


class PipelineError(ValueError):
    pass


def load_config(path: Path) -> tuple[RunConfig, Path]:
    """Read ragkit.yaml. Relative paths inside it are relative to the file's folder."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PipelineError(f"Cannot read {path.name} ({type(error).__name__})") from None
    if not isinstance(raw, dict):
        raise PipelineError(f"{path.name} must contain a mapping of settings")
    try:
        config = RunConfig.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise PipelineError(f"{path.name}: {where}: {first['msg']}") from None
    base = path.resolve().parent

    def rooted(p: Path) -> Path:
        return p if p.is_absolute() else base / p

    config.target.config = rooted(config.target.config)
    if config.target.repo is not None:
        config.target.repo = rooted(config.target.repo)
    config.corpus = rooted(config.corpus)
    config.dataset = rooted(config.dataset)
    config.output = rooted(config.output)
    return config, base


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _output_would_dirty_repo(config: RunConfig) -> bool:
    """True if ragkit's output folder is inside the target repo and git would not ignore it."""
    repo = config.target.repo
    assert repo is not None
    try:
        config.output.resolve().relative_to(repo.resolve())
    except ValueError:
        return False  # outside the repository: cannot make it dirty
    probe = config.output.resolve() / "dev" / "predictions.jsonl"
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), "check-ignore", "-q", str(probe)],
        capture_output=True,
        check=False,
    )
    return result.returncode != 0


def _ragkit(*args: str) -> tuple[int, str, str]:
    """Run the same CLI a person would use. Returns (exit code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "rag_eval_kit.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _shown(*args: str) -> str:
    return "ragkit " + " ".join(f'"{a}"' if " " in a else a for a in args)


DATASET_HELP = [
    "No frozen dataset yet. A person has to do this part; ragkit will not do it for you:",
    "1. Get candidate questions: `ragkit dataset import <your questions> --corpus-dir <corpus> "
    "--output-dir <new folder>` for your own project, or `ragkit dataset generate` for the "
    "bundled FastAPI benchmark.",
    "2. Open review.csv and write yes or no in the keep column of every row.",
    "3. `ragkit dataset review review.csv --corpus-dir <corpus>` to check the sheet.",
    "4. `ragkit dataset freeze review.csv --corpus-dir <corpus> --output-dir <dataset> "
    '--approved-by "<your name>"`.',
    "Then run `ragkit run` again: it carries on from here.",
]


def run_pipeline(
    config_path: Path, *, split: Split = "dev", confirm_heldout: bool = False, dry_run: bool = False
) -> dict:
    """Run the lexical pipeline. Returns a JSON-able summary; ``status`` says why it stopped."""
    stages: list[dict] = []

    def result(status: str, **extra: object) -> dict:
        return {"status": status, "split": split, "stages": stages, **extra}

    def stage(name: str, state: str, **extra: object) -> None:
        stages.append({"stage": name, "state": state, **extra})

    try:
        config, _ = load_config(config_path)
    except PipelineError as error:
        return result("blocked", reason=str(error))
    stage("config", "done", file=config_path.name)

    if split == "heldout" and not confirm_heldout:
        return result(
            "blocked",
            reason="The held-out split is for one final run, after the change and thresholds "
            "are fixed. Add --confirm-heldout if that is what you are doing.",
        )

    try:
        _, docs, corpus_hash = load_corpus(config.corpus)
    except CorpusError as error:
        return result("blocked", reason=str(error))
    stage("corpus", "done", documents=len(docs), corpus_sha256=corpus_hash)

    freeze_file = config.dataset / "freeze.json"
    split_file = config.dataset / f"{split}.jsonl"
    if not freeze_file.exists() or not split_file.exists():
        return result("waiting_for_human", gate="golden_set_review", what_to_do=DATASET_HELP)
    try:
        manifest = json.loads(freeze_file.read_text(encoding="utf-8"))
        expected_hash = manifest[f"{split}_sha256"]
    except (OSError, ValueError, KeyError):
        return result("blocked", reason="freeze.json is unreadable or incomplete")
    if manifest.get("corpus_sha256") != corpus_hash:
        return result("blocked", reason="The corpus changed since the dataset was frozen")
    if _sha256(split_file) != expected_hash:
        return result("blocked", reason=f"{split}.jsonl changed since it was frozen")
    cases = _count_lines(split_file)
    stage(
        "dataset",
        "done",
        approved=manifest.get("review_status"),
        questions=cases,
        dataset_sha256=expected_hash,
    )

    if config.target.repo is not None:
        try:
            checked = verify_revision(config.target.repo, config.revision or "HEAD")
        except RevisionError as error:
            return result("blocked", reason=str(error))
        revision = checked["commit"]
    elif config.revision and config.target.allow_unverified_target:
        revision = config.revision
    else:
        return result(
            "blocked",
            reason="Set target.repo (a clean local git checkout of the system under test) in "
            "ragkit.yaml, or set both revision and target.allow_unverified_target: true.",
        )
    if config.target.repo is not None and _output_would_dirty_repo(config):
        return result(
            "blocked",
            reason=f"The output folder ({config.output}) is inside the target repository and "
            "git does not ignore it, so the files ragkit writes would make the repository "
            "'dirty' and the run would be refused part-way. Add the folder to the "
            "repository's .gitignore and commit that, or set 'output' to a folder outside it.",
        )
    stage("revision", "done", target_revision=revision)

    out = config.output / split
    preds = out / "predictions.jsonl"
    run_file = out / "run-lexical.json"
    report_file = out / "report.md"

    predict_args = [
        "predict", str(split_file),
        "--adapter", config.target.adapter,
        "--adapter-config", str(config.target.config),
        "--target-revision", revision,
        "--output", str(preds),
    ]  # fmt: skip
    if config.target.adapter == "builder":
        predict_args += ["--corpus-dir", str(config.corpus)]
    evaluate_args = [
        "evaluate", str(preds),
        "--output", str(run_file),
        "--target-revision", revision,
        "--dataset-hash", expected_hash,
        "--corpus-hash", corpus_hash,
        "--retrieval-mode", "lexical",
    ]  # fmt: skip
    if config.target.repo is not None:
        evaluate_args += ["--target-repo", str(config.target.repo)]
    else:
        evaluate_args += ["--allow-unverified-target"]
    report_args = ["report", str(run_file), "--output", str(report_file)]

    if dry_run:
        stage(
            "predict",
            "would_run" if not preds.exists() else "would_skip",
            command=_shown(*predict_args),
        )
        stage(
            "evaluate",
            "would_run" if not run_file.exists() else "would_skip",
            command=_shown(*evaluate_args),
        )
        stage(
            "report",
            "would_run" if not report_file.exists() else "would_skip",
            command=_shown(*report_args),
        )
        return result("dry_run")

    out.mkdir(parents=True, exist_ok=True)

    if preds.exists():
        if _count_lines(preds) != cases:
            return result(
                "blocked",
                reason=f"{preds} does not have one prediction per question. Move it away to "
                "start this step again.",
            )
        first = json.loads(preds.read_text(encoding="utf-8").splitlines()[0])
        if first.get("target_revision") != revision:
            return result(
                "blocked",
                reason="Existing predictions are for a different revision. Use a new "
                "'output' folder in ragkit.yaml for this revision.",
            )
        stage("predict", "skipped_already_done", file=str(preds))
    else:
        code, stdout, stderr = _ragkit(*predict_args)
        if code != 0:
            if preds.exists():
                partial = preds.with_suffix(".partial.jsonl")
                preds.replace(partial)
            return result(
                "blocked",
                reason="The target failed on some questions. Failed questions are never dropped.",
                failed_stage="predict",
                command=_shown(*predict_args),
                detail=(stdout or stderr)[-1500:],
            )
        stage("predict", "done", command=_shown(*predict_args), file=str(preds))

    if run_file.exists():
        stage("evaluate", "skipped_already_done", file=str(run_file))
    else:
        code, stdout, stderr = _ragkit(*evaluate_args)
        if code != 0:
            return result(
                "blocked",
                failed_stage="evaluate",
                command=_shown(*evaluate_args),
                detail=(stdout or stderr)[-1500:],
            )
        stage("evaluate", "done", command=_shown(*evaluate_args), file=str(run_file))

    if report_file.exists():
        stage("report", "skipped_already_done", file=str(report_file))
    else:
        code, stdout, stderr = _ragkit(*report_args)
        if code != 0:
            return result(
                "blocked",
                failed_stage="report",
                command=_shown(*report_args),
                detail=(stdout or stderr)[-1500:],
            )
        stage("report", "done", command=_shown(*report_args), file=str(report_file))

    return result(
        "completed",
        paid_calls=0,
        next_steps=[
            "This run used the free lexical track (source matching only).",
            "Paid judge scoring is a separate step you approve yourself: "
            "`ragkit plan`, then `ragkit evaluate ... --live --approve-paid`.",
            "Agree your pass rules before looking at results, then `ragkit compare`.",
        ],
    )
