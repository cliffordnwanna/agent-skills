"""Strict JSON Lines import and export for portable evaluation records."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from rag_eval_kit.models import EvaluationRecord


class JSONLRecordError(ValueError):
    pass


def read_jsonl(path: Path) -> list[EvaluationRecord]:
    records: list[EvaluationRecord] = []
    seen: set[tuple[str, int]] = set()
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as error:
        raise JSONLRecordError(f"Cannot read JSONL input: {type(error).__name__}") from None
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise JSONLRecordError(f"Blank JSONL line at {line_number}")
            try:
                record = EvaluationRecord.model_validate_json(line)
            except (ValidationError, ValueError):
                raise JSONLRecordError(f"Invalid evaluation record at line {line_number}") from None
            key = (record.question_id, record.repeat)
            if key in seen:
                raise JSONLRecordError(
                    f"Duplicate question_id/repeat at line {line_number}: "
                    f"{record.question_id}/{record.repeat}"
                )
            seen.add(key)
            records.append(record)
    if not records:
        raise JSONLRecordError("JSONL input contains no evaluation records")
    return records


def write_jsonl(
    path: Path, records: Iterable[EvaluationRecord], *, overwrite: bool = False
) -> None:
    validated: list[EvaluationRecord] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        key = (record.question_id, record.repeat)
        if key in seen:
            raise JSONLRecordError(
                f"Duplicate question_id/repeat: {record.question_id}/{record.repeat}"
            )
        seen.add(key)
        validated.append(record)
    if not validated:
        raise JSONLRecordError("Refusing to write an empty evaluation file")

    mode = "w" if overwrite else "x"
    try:
        with path.open(mode, encoding="utf-8", newline="\n") as handle:
            for record in validated:
                handle.write(record.model_dump_json() + "\n")
    except OSError as error:
        raise JSONLRecordError(f"Cannot write JSONL output: {type(error).__name__}") from None
