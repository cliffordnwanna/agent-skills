# FastAPI documentation benchmark candidate set

This is a **candidate** dataset, not an approved or frozen benchmark. The source subset is six English tutorial Markdown files from FastAPI commit `05e6df7e906c3decba377c37548019973f40bf15`, licensed under MIT. The copied upstream license is in `LICENSE.upstream.txt`; source paths, URLs, source hashes and corpus hashes are in `provenance.json`.

The corpus is 43,355 characters across six documents, below the Builder's limit of 20 items, 50,000 characters per item and 100,000 total characters. These markdown files are copied verbatim; source excerpts cited by candidate questions are exact strings from them.

## Review

Open `candidates/review.csv` and decide each row:

- Set `keep` to `yes` or `no`.
- Correct or improve the question/reference answer/evidence/source IDs if needed.
- Add reviewer notes and your reviewer name or initials.
- For unanswerable cases, verify the answer is not supported by any document in the provided corpus; `reference_evidence` and `expected_source_ids` should remain empty.

The parallel `candidates/candidate_questions.jsonl` is the canonical machine-readable candidate export. Do not treat blank `keep` values as approval. Do not freeze or split the dataset until the user has reviewed it. After review, validate exact evidence spans and source IDs, freeze with fixed seed and hashes, then create the dev/held-out split. Never tune against held-out cases.

The candidates were authored offline from the cited documentation; no external model call was used to generate them. Candidate validity, answer quality and usefulness have **not** been independently reviewed.
