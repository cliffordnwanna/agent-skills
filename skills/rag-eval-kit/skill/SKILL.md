---
name: rag-eval-kit
description: Guide an honest before-and-after evaluation of a RAG (retrieval-augmented generation) app with the ragkit command-line tool. Use when the user wants to check whether a change made their RAG app better, build or review a set of test questions, run their app against it, score the answers, or compare two versions. Never approves the questions itself, never starts a paid call without the user's clear yes, and never states results that a run did not produce.
---

# RAG Eval Kit skill (v0.1)

**Status: v0.1. The workflow is verified offline. There is no real before-and-after case study yet.** The tool's tests pass and its free commands run. A full evaluation of a real app has not been done, so this skill makes no claim about how well any app performs.

`ragkit` is a free command-line tool. It answers one question: **did my change make my RAG app better?** You help a person use it. A RAG app looks up passages in documents, then writes an answer from them. This skill is for text-based RAG only.

Read `references/disclosures.md` before running anything. It says what the tool sends over the network, what costs money, and what stays on the computer.

## Rules that never bend

1. **A person approves the questions. You never do.** Do not write `yes` in the `keep` column for them. Do not run `dataset freeze` with an approver name they did not give you. Do not call questions "reviewed" when a person has not read them. Pre-screen notes and your own opinions are advice, not approval (`references/golden-set-rubric.md`). You may draft candidate questions if the user asks. They stay unapproved until a person reads each one.
2. **No paid call without a clear yes in this conversation.** `--live` and `--approve-paid` are the user's decision. Run `ragkit plan` first, show the estimate and the cap, and wait for a yes. The default cap is zero, which blocks paid calls. Never raise the cap yourself.
3. **Never claim a result that a run did not produce.** Do not quote scores, gains or "typical" numbers. Report only what a run file or `compare` output from this session contains. Name its dataset fingerprint, target revision and judge. If there is no frozen run, say so.
4. **Use the held-out set once.** Study and fix problems with the dev set. Run the held-out set only at the end, after the change and the pass rules are fixed. Running it again until it looks good makes it worthless (`references/failure-playbook.md`).
5. **Agree the pass rules before looking at results.** The verdict follows those rules, not whichever number went up (`references/threshold-guide.md`).
6. **Do not change scoring code between a baseline and the run it is compared with.** Every run records the evaluator's own commit (`evaluator_revision`). If the scoring code changed, the baseline must be run again.
7. **Say plainly what failed and what is missing.** Failed questions, "not assessable" scores, wide ranges and refused comparisons go in the report, not in a footnote.
8. **No secrets in files or chat.** Keys come from environment variables. Never paste a key anywhere.
9. **Text RAG only.** Say so if the user's app is not text RAG.

## The steps

Run `ragkit <command> --help` for every option. Do not guess flags. Say who does each step, as in this list.

1. **Check the tool.** `ragkit doctor` and `ragkit smoke` need no key and cost nothing. Suggest them first.
2. **Set up.** `ragkit init` writes `ragkit.yaml` and `adapter.json` in the project folder. It never overwrites. It asks before copying this skill anywhere. Do not answer that question for the user.
3. **Connect the app.** Help the user edit `adapter.json` so it matches their app. If the app needs a different request body, add a `request` template (`${question}` is replaced). Then run `ragkit adapter test --adapter-config adapter.json`. This sends **one real question** to the app and shows what was read from the answer. If a path is wrong, it lists the names in the response so the path can be fixed. Tell the user before you run it, because it contacts their app.
4. **Describe the documents.** `ragkit corpus init <folder> --name ... --license ... --license-url ... --source-repository ...` writes `provenance.json` for `.md` and `.txt` files. The documents are limited to 20 files and 100,000 characters in total. `ragkit corpus inspect <folder>` checks the fingerprints. If a fingerprint check fails, stop: the files changed. Do not edit the corpus files or the fingerprints.
5. **Get the questions.** For the bundled FastAPI benchmark: `ragkit dataset generate --corpus-dir ... --output-dir ...`. For the user's own project: `ragkit dataset import <questions.jsonl> --corpus-dir ... --output-dir ...`. Both write `review.csv` with an empty `keep` column. Nothing is approved.
6. **A person reviews.** The user reads every row and writes `yes` or `no` in `keep`, using `references/golden-set-rubric.md`. `ragkit dataset review <csv> --corpus-dir ...` checks the sheet. Blank rows are an error.
7. **A person freezes.** Only after the user says the sheet is approved, and gives their name: `ragkit dataset freeze <csv> --corpus-dir ... --output-dir <new folder> --approved-by "<their name>"`. A frozen folder is never overwritten. It holds `dev.jsonl`, `heldout.jsonl`, `golden.jsonl` and `freeze.json` with fingerprints.
8. **Run the free scoring.** Fill in `ragkit.yaml`, then `ragkit run`. It checks the corpus and the frozen questions, asks the app each dev question, scores for free, and writes a report. It prints the exact commands it used. It stops with `waiting_for_human` until the questions are frozen, and picks up from the files already written if run again. It refuses an app with uncommitted changes, and an output folder inside that app's repository unless git ignores it. Its scoring checks whether the right source documents were retrieved (each document counts once, even if the app returns several chunks of it). It does not judge answer quality. It also records how long each question took (measured on the user's side), how many failed or timed out, and token counts if the app reports them. If some questions fail it stops; `--allow-failures` scores the rest and counts the failures in the error rate. Only use that flag if the user agrees.
9. **Agree pass rules and ceilings** before looking at results (`references/threshold-guide.md`). Ceilings (slowest-answer time, error rate, cost per question) go in `thresholds.yaml` and are checked by `ragkit run` and `ragkit evaluate --thresholds`. Cost needs the app's prices in a pricing file (`--pricing`) that the user supplies. Never guess prices.
10. **Optional paid judge scoring.** `ragkit plan --config <judge.json>` first. Then, only after a clear yes: `ragkit evaluate ... --retrieval-mode semantic --live --approve-paid --config <judge.json> --budget-usd <cap>`.
11. **Compare and report.** `ragkit compare <before.json> <after.json> --pass-metric ... --pass-threshold ...` using the agreed values, then `ragkit report <run.json>`. Runs made with different questions, documents, judges or retrieval modes are refused. Do not override that without telling the user how it weakens the result.
12. **Write up** with `references/report-template.md`. Include the limits in `references/methodology.md`.

## Free, safe first steps

`ragkit doctor` and `ragkit smoke` (a fake app on the same computer, no paid calls) need no key and cost nothing. `ragkit corpus inspect benchmarks/fastapi-docs` needs a clone of the repository, because the benchmark files are not part of the installed package.

## Installing this skill

Run `ragkit init` (it asks first), or copy this `skill/` folder (`SKILL.md` and `references/`) into your assistant's skills folder as `rag-eval-kit`. It does not need the tests or the source code. Install the `ragkit` tool separately; see the repository README.

## References (open one only when a step needs it)

- `references/disclosures.md`: network calls, OpenAI calls, costs, what data is sent.
- `references/golden-set-rubric.md`: how a person should check each question.
- `references/methodology.md`: what is measured and how.
- `references/threshold-guide.md`: how to agree pass rules before running.
- `references/failure-playbook.md`: what to do when something fails or looks wrong.
- `references/report-template.md`: the write-up outline.
