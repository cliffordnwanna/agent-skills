"""Bring your own documents and questions: corpus provenance and question import.

Nothing here calls a model or the network. Imported questions are never approved: they are
written to a review sheet with an empty ``keep`` column, and a person must decide every row
before ``dataset freeze`` will accept them.
"""

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from rag_eval_kit.corpus import CorpusError, load_corpus
from rag_eval_kit.models import CorpusManifest, EvaluationCase

DOC_SUFFIXES = {".md", ".txt"}
_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_.:-]+")


class QuestionImportError(ValueError):
    """Raised when a question file cannot be imported."""


def _git_head(directory: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(directory), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = result.stdout.strip()
    return head if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", head) else None


def init_corpus(
    directory: Path,
    *,
    name: str,
    license_name: str,
    license_url: str,
    source_repository: str,
    source_revision: str | None,
) -> dict:
    """Write ``provenance.json`` for the .md and .txt files under ``directory``.

    Existing provenance is never overwritten. The result is re-loaded through
    ``load_corpus`` so the same size limits and hash checks apply as for any corpus.
    """
    target = directory / "provenance.json"
    if target.exists():
        raise CorpusError("provenance.json already exists; it is never overwritten")
    revision = source_revision or _git_head(directory)
    if revision is None:
        raise CorpusError(
            "Pass --source-revision with a 40-character commit SHA (or a content hash) "
            "that identifies this version of the documents"
        )
    root = directory.resolve()
    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in DOC_SUFFIXES
        and not any(part.startswith(".") for part in p.relative_to(root).parts)
    )
    if not files:
        raise CorpusError("No .md or .txt documents found in the corpus directory")
    documents = []
    seen: set[str] = set()
    for path in files:
        relative = PurePosixPath(path.relative_to(root).as_posix())
        source_id = _UNSAFE_ID.sub("-", relative.stem).strip("-")[:128] or "doc"
        if source_id in seen:
            raise CorpusError(f"Two documents map to the same source ID: {source_id}")
        seen.add(source_id)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        documents.append(
            {
                "source_id": source_id,
                "title": relative.stem[:200] or source_id,
                "source_url": str(relative),
                "source_path": str(relative),
                "source_sha256": digest,
                "content_sha256": digest,
            }
        )
    try:
        manifest = CorpusManifest(
            name=name,
            source_repository=source_repository,
            source_revision=revision,
            license=license_name,
            license_url=license_url,
            documents=documents,
            transformations=["Files used exactly as provided; no transformation."],
        )
    except ValidationError as error:
        raise CorpusError(f"Invalid corpus details: {error.errors()[0]['msg']}") from None
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest.model_dump(mode="json"), handle, indent=2)
    try:
        load_corpus(directory)
    except CorpusError:
        target.unlink(missing_ok=True)
        raise
    return {"documents": [d["source_id"] for d in documents], "count": len(documents)}


def _json_list(value: object, field: str, number: int) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise QuestionImportError(f"Row {number}: {field} is not valid JSON") from None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise QuestionImportError(f"Row {number}: {field} must be a list of strings")
    return value


def _to_case(raw: dict, number: int) -> EvaluationCase:
    unanswerable_raw = raw.get("unanswerable", False)
    unanswerable = (
        unanswerable_raw.strip().lower() == "true"
        if isinstance(unanswerable_raw, str)
        else bool(unanswerable_raw)
    )
    evidence = raw.get("reference_evidence", raw.get("reference_evidence_json"))
    sources = raw.get("expected_source_ids", raw.get("expected_source_ids_json"))
    answer = (raw.get("reference_answer") or "").strip()
    if not answer and unanswerable:
        answer = "The corpus does not answer this question."
    try:
        return EvaluationCase(
            question_id=(raw.get("question_id") or "").strip() or f"q-{number:03d}",
            category=(raw.get("category") or "").strip()
            or ("unanswerable" if unanswerable else "direct"),
            question=(raw.get("question") or "").strip(),
            reference_answer=answer,
            reference_evidence=_json_list(evidence, "reference_evidence", number),
            expected_source_ids=_json_list(sources, "expected_source_ids", number),
            unanswerable=unanswerable,
        )
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(p) for p in first["loc"])
        raise QuestionImportError(
            f"Row {number}: invalid {field or 'row'}: {first['msg']}"
        ) from None


def read_question_file(path: Path) -> list[EvaluationCase]:
    """Read your own questions from JSONL or from a CSV in the review-sheet format.

    JSONL: one object per line with ``question``, ``reference_answer``,
    ``reference_evidence`` (verbatim spans), ``expected_source_ids`` and optional
    ``question_id``, ``category``, ``unanswerable``. CSV: the same columns as
    ``review.csv``. The ``keep``, ``reviewer`` and ``review_notes`` columns are ignored:
    approval always has to be given again by a person.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise QuestionImportError(f"Cannot read question file ({type(error).__name__})") from None
    rows: list[dict] = []
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    else:
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                raise QuestionImportError(f"Line {number} is not valid JSON") from None
            if not isinstance(item, dict):
                raise QuestionImportError(f"Line {number} must be a JSON object")
            rows.append(item)
    if not rows:
        raise QuestionImportError("The question file has no questions")
    return [_to_case(row, number) for number, row in enumerate(rows, 1)]
