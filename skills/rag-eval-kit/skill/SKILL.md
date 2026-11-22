---
name: rag-eval-kit
description: Guide an honest before/after evaluation of a RAG (retrieval-augmented generation) application using the ragkit command-line tool. Use when the user wants to build or review a golden question set, run their RAG app against it, score retrieval and answers, compare two versions of the system, or write up whether a change helped. Never approves the golden set itself, never runs paid calls without the user's explicit approval, and never states results that have not been produced by a frozen run.
---

# RAG Eval Kit skill (v0.1)

**Status: v0.1. The workflow is verified offline; there is no live case study yet.** The tool's own tests pass and its offline commands run. A full before/after evaluation of a real system has not been completed, so this skill makes no claim about how well any system performs.

This skill guides a person through `ragkit`, a local command-line tool (Python, Apache-2.0) that asks one question: **did this change make my RAG application better?** It does not replace the person's judgement. Read `references/disclosures.md` first: it states what the tool sends over the network, what costs money, and what stays local.

## Rules that never bend

1. **The human approves the golden set. You never do.** Do not fill the `keep` column for the user, do not run `dataset freeze` with an approver name the user did not give you, and do not describe model-drafted or pre-screened questions as reviewed. Pre-screen notes are recommendations, not approval (`references/golden-set-rubric.md`).
2. **No paid call without explicit approval in this conversation.** `--live` and `--approve-paid` are the user's decision. Estimate cost first with `ragkit plan`, show the figure and the cap, and wait for a yes. The default budget is zero, which blocks paid calls. Never raise a cap on your own.
3. **Never claim a result you have not produced.** Do not quote scores, improvements or "typical" numbers. Report only what a run file or `compare` output in this session contains, with its dataset hash, target revision and judge. If no frozen run exists, say so.
4. **Use the held-out split once.** Diagnose and fix on the dev split. Run held-out only after the change and the thresholds are frozen. Re-running held-out until it looks good invalidates it (`references/failure-playbook.md`).
5. **Agree thresholds before looking at results.** A verdict follows the pre-agreed rule, not whichever metric improved (`references/threshold-guide.md`).
6. **Report failures and gaps plainly.** Failed questions, unassessable metrics, wide intervals and incompatible runs go in the report, not in a footnote.
7. **No secrets in files or chat.** Keys come from environment variables. Never paste a key into a file, a commit, or the conversation.
8. **Text RAG only.** Say so when the user's system is not text RAG.

## The workflow (run from `skills/rag-eval-kit/` in a clone, or anywhere after installing the package)

Run `ragkit <command> --help` for every option; do not guess flags.

1. **Setup and doctor.** `ragkit doctor` checks local dependencies and makes no API calls. It reports `provider_connectivity: UNVERIFIED` by design.
2. **Corpus.** `ragkit corpus inspect <dir>` verifies document hashes, licence and size limits against `provenance.json`. If the hash check fails, stop: the bytes changed (often line endings). Do not edit corpus files.
3. **Candidates.** `ragkit dataset generate --corpus-dir <dir> --output-dir <new dir>` writes unreviewed candidates and `review.csv`.
4. **Human review (the user).** The user fills `keep` (yes/no) for every row and fixes wording. Guide them with `references/golden-set-rubric.md`. `ragkit dataset review <csv> --corpus-dir <dir>` validates the sheet; blank rows are an error.
5. **Freeze (only after the user says the sheet is approved, and gives their name).** `ragkit dataset freeze <csv> --corpus-dir <dir> --output-dir <new dir> --approved-by "<their name>"`. Frozen directories are never overwritten. It writes `golden.jsonl`, `dev.jsonl`, `heldout.jsonl` and `freeze.json` with hashes and the split seed.
6. **Predict.** `ragkit predict <dev.jsonl> --adapter generic|builder --adapter-config <cfg.json> --target-revision <git sha> --output <preds.jsonl>`. This calls the user's own RAG app. Failed questions make the command exit non-zero; none are dropped silently. `--target-revision` must be the exact revision tested.
7. **Evaluate.**
   - Offline: `ragkit evaluate <preds.jsonl> --retrieval-mode lexical --output <run.json> --target-revision ... --dataset-hash ... --corpus-hash ...` (free, deterministic; retrieval metrics only).
   - Paid: add `--retrieval-mode semantic --live --approve-paid --config <judge.json> --budget-usd <cap>` only after rule 2.
8. **Compare and report.** `ragkit compare <before.json> <after.json>`, with `--pass-metric` and `--pass-threshold` set to the pre-agreed values; then `ragkit report <run.json>`. Runs with different datasets, corpora, judges or retrieval modes are refused unless overridden; do not override without telling the user why that weakens the comparison.
9. **Write-up.** Use `references/report-template.md`. Include the limits listed in `references/methodology.md`.

## Free, safe first steps

`ragkit doctor` and `ragkit smoke` (a local mock server, zero paid calls) need no key and no spend, and work from the installed package. `ragkit corpus inspect benchmarks/fastapi-docs` needs a clone of the repository, because the benchmark files are not part of the installed package. Suggest these before anything else.

## Installing this skill

Copy only this `skill/` folder (it contains `SKILL.md` and `references/`) into your assistant's skills directory, named `rag-eval-kit`. It does not need the tests or the source tree. The `ragkit` tool itself is installed separately; see the repository README.

## References (load only when a step needs them)

- `references/disclosures.md`: network calls, OpenAI calls, costs, data sent, local files.
- `references/golden-set-rubric.md`: how the user should review each question.
- `references/methodology.md`: what is measured and which statistics are used.
- `references/threshold-guide.md`: how to agree pass rules before running.
- `references/failure-playbook.md`: what to do when something fails or looks wrong.
- `references/report-template.md`: the write-up skeleton.
