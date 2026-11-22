import csv
import json

import pytest
from typer.testing import CliRunner

from rag_eval_kit.cli import app
from rag_eval_kit.corpus import load_corpus

runner = CliRunner()
REV = "a" * 40

DOC_A = "The orders service stores every order in a table named orders_v2.\n"
DOC_B = "Refunds are issued within five working days of approval.\n"

GOOD = [
    {
        "question": "Which table holds orders?",
        "reference_answer": "orders_v2",
        "reference_evidence": ["a table named orders_v2"],
        "expected_source_ids": ["orders"],
    },
    {
        "question": "How fast are refunds?",
        "reference_answer": "Within five working days of approval.",
        "reference_evidence": ["within five working days"],
        "expected_source_ids": ["refunds"],
        "category": "paraphrased",
    },
    {"question": "Who is the CEO?", "unanswerable": True},
]


def init(corpus, *extra):
    return runner.invoke(
        app,
        [
            "corpus", "init", str(corpus),
            "--name", "My docs", "--license", "proprietary",
            "--license-url", "internal", "--source-repository", "internal",
            *extra,
        ],
    )  # fmt: skip


def import_(src, corpus, out):
    return runner.invoke(
        app,
        ["dataset", "import", str(src), "--corpus-dir", str(corpus), "--output-dir", str(out)],
    )


def review_(sheet, corpus):
    return runner.invoke(app, ["dataset", "review", str(sheet), "--corpus-dir", str(corpus)])


def freeze_(sheet, corpus, out):
    return runner.invoke(
        app,
        [
            "dataset", "freeze", str(sheet),
            "--corpus-dir", str(corpus), "--output-dir", str(out),
            "--approved-by", "Reviewer",
        ],
    )  # fmt: skip


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def read_sheet(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_sheet(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def corpus(tmp_path):
    folder = tmp_path / "docs"
    (folder / "sub").mkdir(parents=True)
    (folder / "orders.md").write_text(DOC_A, encoding="utf-8")
    (folder / "sub" / "refunds.txt").write_text(DOC_B, encoding="utf-8")
    (folder / ".hidden.md").write_text("ignored", encoding="utf-8")
    return folder


@pytest.fixture
def ready(corpus):
    result = init(corpus, "--source-revision", REV)
    assert result.exit_code == 0, result.output
    return corpus


def test_corpus_init_writes_valid_provenance(corpus):
    result = init(corpus, "--source-revision", REV)
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["documents"] == ["orders", "refunds"]  # hidden file skipped, subfolder included
    _, docs, corpus_hash = load_corpus(corpus)
    assert len(docs) == 2 and len(corpus_hash) == 64


def test_corpus_init_never_overwrites(ready):
    again = init(ready, "--source-revision", REV)
    assert again.exit_code == 2 and "never overwritten" in again.stdout


def test_corpus_init_needs_a_revision_outside_git(corpus):
    result = init(corpus)  # the temp folder is not a git repository
    assert result.exit_code == 2 and "--source-revision" in result.stdout
    assert not (corpus / "provenance.json").exists()


def test_corpus_init_rejects_bad_revision(corpus):
    result = init(corpus, "--source-revision", "short")
    assert result.exit_code == 2
    assert not (corpus / "provenance.json").exists()


def test_corpus_init_rejects_empty_folder(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = init(empty, "--source-revision", REV)
    assert result.exit_code == 2 and "No .md or .txt" in result.stdout


def test_import_jsonl_writes_review_sheet_with_blank_keep(ready, tmp_path):
    src = tmp_path / "q.jsonl"
    write_jsonl(src, GOOD)
    out_dir = tmp_path / "cand"
    result = import_(src, ready, out_dir)
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["status"] == "questions_imported" and out["review_required"] is True
    rows = read_sheet(out_dir / "review.csv")
    assert [r["question_id"] for r in rows] == ["q-001", "q-002", "q-003"]
    assert all(r["keep"] == "" for r in rows)  # never pre-approved
    assert rows[2]["category"] == "unanswerable" and rows[2]["unanswerable"] == "true"


def test_import_ignores_approval_columns_in_csv(ready, tmp_path):
    src = tmp_path / "first.jsonl"
    write_jsonl(src, GOOD)
    import_(src, ready, tmp_path / "c1")
    rows = read_sheet(tmp_path / "c1" / "review.csv")
    for row in rows:
        row["keep"], row["reviewer"] = "yes", "someone"
    pre_approved = tmp_path / "pre_approved.csv"
    write_sheet(pre_approved, rows)
    result = import_(pre_approved, ready, tmp_path / "c2")
    assert result.exit_code == 0, result.output
    again = read_sheet(tmp_path / "c2" / "review.csv")
    assert all(r["keep"] == "" and r["reviewer"] == "" for r in again)


def _bad_evidence(r):
    r[0].update(reference_evidence=["text that is not in the docs"])


def _bad_source(r):
    r[0].update(expected_source_ids=["nope"])


def _no_source(r):
    r[0].update(expected_source_ids=[])


def _unanswerable_with_evidence(r):
    r[2].update(reference_evidence=["x"], expected_source_ids=["orders"])


def _duplicate_question(r):
    r[1].update(question=r[0]["question"])


def _bad_category(r):
    r[0].update(category="made_up")


def _no_question(r):
    r[0].pop("question")


@pytest.mark.parametrize(
    "mutation,message",
    [
        (_bad_evidence, "absent"),
        (_bad_source, "Unknown source"),
        (_no_source, "missing evidence"),
        (_unanswerable_with_evidence, "Unanswerable"),
        (_duplicate_question, "unique"),
        (_bad_category, "category"),
        (_no_question, "question"),
    ],
)
def test_import_rejects_bad_questions(ready, tmp_path, mutation, message):
    rows = json.loads(json.dumps(GOOD))
    mutation(rows)
    src = tmp_path / "q.jsonl"
    write_jsonl(src, rows)
    out_dir = tmp_path / "cand"
    result = import_(src, ready, out_dir)
    assert result.exit_code == 2, result.output
    assert message.lower() in result.stdout.lower()
    assert not (out_dir / "review.csv").exists()


def test_import_never_overwrites(ready, tmp_path):
    src = tmp_path / "q.jsonl"
    write_jsonl(src, GOOD)
    assert import_(src, ready, tmp_path / "cand").exit_code == 0
    second = import_(src, ready, tmp_path / "cand")
    assert second.exit_code == 2 and "never overwrite" in second.stdout


def test_import_rejects_invalid_json_line(ready, tmp_path):
    src = tmp_path / "q.jsonl"
    src.write_text("{not json}\n", encoding="utf-8")
    result = import_(src, ready, tmp_path / "o")
    assert result.exit_code == 2 and "not valid JSON" in result.stdout


def test_imported_questions_need_human_approval_then_freeze(ready, tmp_path):
    src = tmp_path / "q.jsonl"
    write_jsonl(src, GOOD)
    import_(src, ready, tmp_path / "cand")
    sheet = tmp_path / "cand" / "review.csv"
    frozen = tmp_path / "frozen"

    # Not approved yet: review and freeze both refuse.
    assert review_(sheet, ready).exit_code == 2
    refused = freeze_(sheet, ready, frozen)
    assert refused.exit_code == 2 and not frozen.exists()

    # A person decides every row.
    rows = read_sheet(sheet)
    for row in rows:
        row["keep"] = "yes"
    write_sheet(sheet, rows)
    assert review_(sheet, ready).exit_code == 0
    done = freeze_(sheet, ready, frozen)
    assert done.exit_code == 0, done.output
    manifest = json.loads((frozen / "freeze.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["golden"] == 3
    assert manifest["review_status"] == "approved by Reviewer"
