import csv
import shutil
from pathlib import Path

import pytest

from rag_eval_kit.corpus import CorpusError, load_corpus
from rag_eval_kit.dataset import build_candidates, validate_candidates, write_candidate_files

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "benchmarks" / "fastapi-docs"


def test_pinned_corpus_hashes_and_builder_limits():
    manifest, documents, corpus_hash = load_corpus(CORPUS_DIR)
    assert len(manifest.documents) == len(documents) == 6
    assert len(corpus_hash) == 64
    assert sum(len(document.content) for document in documents) <= 100_000
    assert all(len(document.content) <= 50_000 for document in documents)


def test_modified_corpus_document_is_rejected(tmp_path):
    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS_DIR, copied)
    source = copied / "corpus" / "body.md"
    source.write_text(source.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="content hash mismatch"):
        load_corpus(copied)


def test_candidate_set_has_expected_distribution_and_exact_evidence():
    _, documents, _ = load_corpus(CORPUS_DIR)
    candidates = build_candidates()
    assert len(candidates) == 60
    categories = {
        "direct",
        "paraphrased",
        "multi_document",
        "difficult_retrieval",
        "unanswerable",
    }
    assert {
        category: sum(case.category == category for case in candidates) for category in categories
    } == {
        "direct": 12,
        "paraphrased": 12,
        "multi_document": 12,
        "difficult_retrieval": 12,
        "unanswerable": 12,
    }
    validate_candidates(candidates, documents)


def test_candidate_review_export_is_editable_and_exclusive(tmp_path):
    candidates = build_candidates()
    result = write_candidate_files(candidates, tmp_path)
    assert result["question_count"] == "60"
    with (tmp_path / "review.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 60
    assert rows[0]["keep"] == ""
    assert rows[0]["reviewer"] == ""
    assert (tmp_path / "candidate_questions.jsonl").read_text(encoding="utf-8").count("\n") == 60
    with pytest.raises(FileExistsError):
        write_candidate_files(candidates, tmp_path)
