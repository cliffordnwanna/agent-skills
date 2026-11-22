"""Review-sheet ingestion and deterministic, leakage-aware dataset freezing."""

import csv
import hashlib
import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from rag_eval_kit.dataset import validate_candidates
from rag_eval_kit.models import CorpusDocument, EvaluationCase

DATASET_VERSION = "1"


class ReviewError(ValueError):
    pass


def load_review(path: Path, corpus: list[CorpusDocument]) -> tuple[list[EvaluationCase], dict]:
    """Apply the reviewer's edits and keep/drop decisions. Blank decisions are an error."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise ReviewError(f"Cannot read review sheet ({type(error).__name__})") from None
    kept: list[EvaluationCase] = []
    undecided: list[str] = []
    dropped = 0
    for row in rows:
        decision = (row.get("keep") or "").strip().lower()
        if decision not in {"yes", "no"}:
            undecided.append(row.get("question_id", "?"))
            continue
        if decision == "no":
            dropped += 1
            continue
        try:
            kept.append(
                EvaluationCase(
                    question_id=row["question_id"],
                    category=row["category"],
                    question=row["question"],
                    reference_answer=row["reference_answer"],
                    reference_evidence=json.loads(row["reference_evidence_json"] or "[]"),
                    expected_source_ids=json.loads(row["expected_source_ids_json"] or "[]"),
                    unanswerable=row["unanswerable"].strip().lower() == "true",
                )
            )
        except (KeyError, ValueError) as error:
            raise ReviewError(f"Invalid review row {row.get('question_id', '?')}") from error
    if undecided:
        raise ReviewError(
            f"{len(undecided)} rows have no keep=yes/no decision (first: {undecided[:5]})"
        )
    if not kept:
        raise ReviewError("No questions were kept")
    try:
        validate_candidates(kept, corpus)
    except ValueError as error:
        raise ReviewError(str(error)) from None
    summary = {
        "rows": len(rows),
        "kept": len(kept),
        "dropped": dropped,
        "by_category": dict(Counter(c.category for c in kept)),
    }
    return kept, summary


def _groups(cases: list[EvaluationCase]) -> list[list[EvaluationCase]]:
    """Cases sharing an evidence span form one group so they cannot straddle the split."""
    parent = list(range(len(cases)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[str, int] = {}
    for i, case in enumerate(cases):
        for span in case.reference_evidence:
            if span in owner:
                parent[find(i)] = find(owner[span])
            else:
                owner[span] = i
    grouped: dict[int, list[EvaluationCase]] = {}
    for i, case in enumerate(cases):
        grouped.setdefault(find(i), []).append(case)
    return sorted(grouped.values(), key=lambda g: g[0].question_id)


def split_cases(
    cases: list[EvaluationCase], seed: int, heldout_fraction: float = 0.4
) -> tuple[list[EvaluationCase], list[EvaluationCase]]:
    totals = Counter(c.category for c in cases)
    target_held = {k: v * heldout_fraction for k, v in totals.items()}
    groups = _groups(cases)
    random.Random(seed).shuffle(groups)
    groups.sort(key=len, reverse=True)  # stable: ties keep their seeded order
    dev: list[EvaluationCase] = []
    held: list[EvaluationCase] = []
    held_n: Counter = Counter()
    dev_n: Counter = Counter()
    for group in groups:
        cats = Counter(c.category for c in group)
        held_need = sum(target_held[k] - held_n[k] for k in cats)
        dev_need = sum((totals[k] - target_held[k]) - dev_n[k] for k in cats)
        if held_need > dev_need:
            held.extend(group)
            held_n.update(cats)
        else:
            dev.extend(group)
            dev_n.update(cats)
    return sorted(dev, key=lambda c: c.question_id), sorted(held, key=lambda c: c.question_id)


def _write(path: Path, cases: list[EvaluationCase]) -> str:
    content = "".join(c.model_dump_json() + "\n" for c in cases)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def freeze(
    cases: list[EvaluationCase],
    output_dir: Path,
    *,
    corpus_hash: str,
    seed: int,
    approved_by: str,
    review_sheet_sha256: str,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    dev, held = split_cases(cases, seed)
    ordered = sorted(cases, key=lambda c: c.question_id)
    manifest = {
        "dataset_version": DATASET_VERSION,
        "review_status": f"approved by {approved_by}",
        "frozen_at": datetime.now(UTC).isoformat(),
        "split_seed": seed,
        "corpus_sha256": corpus_hash,
        "review_sheet_sha256": review_sheet_sha256,
        "golden_sha256": _write(output_dir / "golden.jsonl", ordered),
        "dev_sha256": _write(output_dir / "dev.jsonl", dev),
        "heldout_sha256": _write(output_dir / "heldout.jsonl", held),
        "counts": {"golden": len(cases), "dev": len(dev), "heldout": len(held)},
        "dev_by_category": dict(Counter(c.category for c in dev)),
        "heldout_by_category": dict(Counter(c.category for c in held)),
        "note": "Held-out split must not be used to diagnose or tune fixes.",
    }
    with (output_dir / "freeze.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest
