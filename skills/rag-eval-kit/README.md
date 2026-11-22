# RAG Eval Kit

**A free command-line tool that checks whether a change to your RAG app made its answers better or worse.**

A RAG app (retrieval-augmented generation) looks up passages in your documents, then writes an answer from them. When you change it, you want proof the change helped. This tool gives you that proof, using questions a person has checked, the same way every time.

> **Status: v0.1. The workflow is verified offline. There is no real before-and-after result yet.** No scores are published, and none should be quoted until a case study exists. See [Status](#status).


## Why use it

- **Stop guessing.** "It feels better" is not evidence. This gives you a fair before-and-after comparison on questions you trust.
- **Catch problems before your users do.** You see which questions got worse, not just an average.
- **Safe by default.** The first steps are free and offline. Nothing paid runs unless you say yes, with a spending cap. A person approves the test questions; the tool never does.
- **Same result every time.** The questions are locked and fingerprinted, the tested version of your app is pinned, and every run records which version of this tool made it.

At the end you get a short written report: what you changed, how the answers moved on questions that were locked in advance, what failed, and how much doubt there is.

## Quick start (about 2 minutes, free)

```bash
uv tool install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"
ragkit smoke
```

`ragkit smoke` starts a tiny fake RAG app on your computer, asks it questions, scores the answers, and prints the result. It needs no key and makes no paid calls. This is what you should see:

```text
✓ Smoke test passed
  A tiny fake RAG app on this computer answered 3 questions and was scored.
  Free retrieval scores: hit@1 1.00  hit@3 1.00  recall@3 1.00  mrr 1.00
  Not assessable here: abstention_accuracy
  Paid calls: 0. No key was needed.

Next: run `ragkit init` in your own project.
```

If you see `✓ Smoke test passed`, the tool works on your machine. With pip instead of uv: `pip install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"`.

Then, in your own project: `ragkit init`. The [workflow](#the-workflow-who-does-what) below shows each step.

> Every command prints a short readable summary with a `Next:` line. Add `--json` anywhere on the command line (for example `ragkit run --json`) to get exact machine-readable output for scripts and AI agents. On a terminal that cannot show checkmarks, `[ok]` and `[x]` are used instead.

## Who it is for

You build or maintain a text-based RAG app and want to measure a change with numbers instead of a feeling. You can use a terminal. You do not need to know statistics: the tool handles that.

## What you need

| Need | Detail |
|---|---|
| Python | 3.12, 3.13 or 3.14 |
| An installer | [uv](https://docs.astral.sh/uv/) (recommended) or pip |
| git | Used to pin the exact version of your app that you tested |
| Operating system | The tests run on Ubuntu and Windows in CI. macOS is not tested. |
| An OpenAI key | **Only** for the optional paid judge steps. Never needed for `ragkit smoke`, `ragkit doctor` or the free scoring. |
| Your RAG app | Text only. It must give back its **answer** and the **passages it retrieved**, either from an HTTP endpoint that returns JSON, or by you writing the results to a JSONL file (one JSON object per line). |

## Does it work with my RAG app?

| Your app | Works? |
|---|---|
| Text RAG with a JSON HTTP endpoint that returns the answer and the retrieved passages | **Works** (generic adapter, with an optional request template) |
| Text RAG where you can write the answer and passages to a JSONL file | **Works** |
| The [Conversational Agent Builder](https://github.com/cliffordnwanna/CONVERSATIONAL_AGENT_BUILDER) | **Works** (its own adapter). Keyword mode was tried against the real app; meaning-based mode is UNVERIFIED |
| Your app returns only an answer, with no retrieved passages | **Works partly.** Scores that need the passages cannot be worked out. They are reported as "not assessable", never as zero. |
| Your app returns its sources as a list of objects (for example `sources: [{"id": ...}]`) | **Works partly.** The response paths only read lists of text, so use the JSONL route or a thin wrapper endpoint. |
| Login through a header (API key or token) | **Works partly.** Headers work, and secrets can come from environment variables. Other login flows do not. |
| More than 20 documents or 100,000 characters of documents in total | **Not yet.** This limit comes from the Builder and still applies. |
| Making questions from **your own documents** automatically | **Not yet.** You write them (or have your agent draft them) and a person approves them. |
| Streaming answers, multi-turn chat, agent tool calls, images, audio | **Not yet** |

## The workflow: who does what

| # | Step | Who | Command |
|---|---|---|---|
| 1 | Describe your app and files | You | `ragkit init` |
| 2 | Check the tool can talk to your app | You | `ragkit adapter test --adapter-config adapter.json` |
| 3 | Describe your documents | You | `ragkit corpus init <folder> ...` |
| 4 | Bring or write your questions | You | `ragkit dataset import ...` |
| 5 | **Read every question and say yes or no** | **A person must do this** | edit `review.csv` |
| 6 | **Approve and lock the question set** | **A person must do this** | `ragkit dataset freeze ... --approved-by "<name>"` |
| 7 | Run the free scoring | Tool | `ragkit run` |
| 8 | **Agree your pass rules before looking at results** | **A person must do this** | write them down |
| 9 | Optional paid judge scoring | Tool, only with your OK | `ragkit evaluate ... --live --approve-paid` |
| 10 | Compare before and after, write the report | Tool | `ragkit compare`, `ragkit report` |

The tool never approves questions, never starts a paid call by itself, and stops with "Waiting for a person" (`waiting_for_human` in `--json`) until step 6 is done.

## Use it with your own project

Run these from your project folder. Every command that writes files refuses to overwrite existing ones.

```bash
ragkit init
```

This writes `ragkit.yaml` (settings) and `adapter.json` (how to talk to your app). It asks before copying the agent skill anywhere, and the default answer is no.

Edit `adapter.json`, then test it. This sends **one real question** to your app and shows what was read from the answer. It saves nothing.

```bash
ragkit adapter test --adapter-config adapter.json
```

If your app wants a different request body, add a template to `adapter.json`. `${question}` is replaced by the question:

```json
"request": {"messages": [{"role": "user", "content": "${question}"}], "stream": false}
```

If the answer is in a different place in the response, set `answer_path` (for example `"choices.0.message.content"`). The same goes for `contexts_path`, `source_ids_path` and `retrieval_mode_path`. `ragkit adapter test` lists the names in the response so you can fix a wrong path.

**Your documents.** Put them in a folder as `.md` or `.txt` files, then:

```bash
ragkit corpus init docs --name "My docs" --license proprietary --license-url internal --source-repository internal
```

If the folder is inside a git repository, the version is taken from git. If not, add `--source-revision <40-character id>`.

**Your questions.** Write them in a JSONL file, one per line:

```json
{"question": "Which table holds orders?", "reference_answer": "orders_v2", "reference_evidence": ["a table named orders_v2"], "expected_source_ids": ["orders"]}
```

`reference_evidence` must be text copied word for word from your documents. For a question your documents cannot answer, write `{"question": "Who is the CEO?", "unanswerable": true}`. Then:

```bash
ragkit dataset import my-questions.jsonl --corpus-dir docs --output-dir candidates
```

This checks each question against your documents and writes `candidates/review.csv` with an empty `keep` column. Nothing is approved yet. A person opens the file, reads every row, and writes `yes` or `no` in `keep`. The rubric is in [skill/references/golden-set-rubric.md](skill/references/golden-set-rubric.md). Then:

```bash
ragkit dataset review candidates/review.csv --corpus-dir docs
ragkit dataset freeze candidates/review.csv --corpus-dir docs --output-dir frozen --approved-by "Your Name"
```

Freezing locks the questions. It splits them into a **dev** set (for finding and fixing problems) and a **held-out** set (kept for one final check), and records fingerprints of every file.

**Run the free scoring.** Put the paths in `ragkit.yaml`, then:

```bash
ragkit run
```

`ragkit run` checks your corpus and frozen questions, asks your app every dev question, scores the answers for free, and writes a report. It prints the exact commands it used. It stops at the points where a person must act, and carries on from the files already written if you run it again. It refuses a target app with uncommitted changes. If the `output` folder in `ragkit.yaml` is inside your app's own repository, add it to that repository's `.gitignore` and commit that first, because the tool's own files would otherwise count as uncommitted changes (`ragkit run` tells you if you forget). Use the held-out set once, at the end: `ragkit run --split heldout --confirm-heldout`.

**Speed, errors and cost.** Besides answer quality, a run records how long each question took (measured on your side, retries included), how many questions failed or timed out, and, if your app reports them, token counts and its own timings. The report shows the median (p50) and slow-end (p95) time, the error rate and the invalid rate. To estimate cost, give the tool your app's prices in a small JSON file (`--pricing`), because it never guesses prices. To set limits agreed in advance, write a `thresholds.yaml`:

```yaml
ceilings:
  latency_p95_ms: 4000     # the slow end of answers must stay under 4 seconds
  error_rate: 0.02         # at most 2% of questions may fail
  invalid_rate: 0.0
  cost_per_query_usd: 0.01
```

Add `thresholds: thresholds.yaml` (and `pricing: pricing.json`) to `ragkit.yaml`, or pass `--thresholds` and `--pricing` to `ragkit evaluate`. A value the tool could not measure is reported as unknown and never counts as passing. If some questions fail, `ragkit run` stops by default; `ragkit run --allow-failures` scores the rest and counts the failures in the error rate. Retrieval scores count each source document once, even when your app returns several chunks of it (`--hit-level chunk` turns that off).

This is what a finished run looks like. The scores here come from a tiny fake app, so they mean nothing about any real system:

```text
✓ ragkit run finished (dev set, free scoring, 0 paid calls)
  ✓ settings       ragkit.yaml
  ✓ documents      2 documents verified
  ✓ questions      2 questions, approved by Your Name
  ✓ app version    bb0dc7b
  ✓ ask your app   predictions.jsonl
  ✓ score answers  run-lexical.json
  ✓ write report   report.md

  Retrieval scores (free: did it find the right documents?): hit@1 0.00  hit@3 0.00
  recall@3 0.00  mrr 0.00
  Not assessable here: abstention_accuracy
  Speed: median 5 ms, slow end 30 ms
  Errors: 0.0% of questions
  Report: ragkit-out\dev\report.md

Next:
  - Paid judge scoring is a separate step you approve yourself: `ragkit plan`, then `ragkit evaluate ... --live --approve-paid`.
  - Agree your pass rules before looking at results, then `ragkit compare`.
```

If a person still has to act, it stops and says so:

```text
… Waiting for a person: the golden set is not frozen yet
  ✓ settings       ragkit.yaml
  ✓ documents      2 documents verified

  No frozen dataset yet. A person has to do this part; ragkit will not do it for you:
  1. Get candidate questions: ...
```

## The FastAPI example benchmark

The repository includes one ready-made benchmark made from public FastAPI documentation, so you can see the whole workflow without writing questions. Clone the repository to use it:

```bash
git clone https://github.com/cliffordnwanna/agent-skills.git
cd agent-skills/skills/rag-eval-kit
uv sync --locked
uv run ragkit corpus inspect benchmarks/fastapi-docs
```

Its 60 candidate questions are **not yet approved or frozen**. This is the only benchmark with built-in questions. For any other project, use `dataset import`.

## What it costs

- **Free:** everything above except step 9. This includes the scoring in `ragkit run`, which checks whether your app retrieved the right source documents.
- **Paid, optional:** the judge (step 9) asks an OpenAI model to grade answers. It needs your OpenAI key in the environment (`RAGKIT_OPENAI_API_KEY`), `--live`, `--approve-paid`, and a spending cap. The cap defaults to **zero**, which blocks paid calls. Run `ragkit plan --config docs/judge.example.json` first for an estimate with no calls.
- The example judge is `gpt-4.1-mini`. Its published price on 2026-11-22 was $0.40 per million input tokens and $1.60 per million output tokens. Check current prices before you rely on this.
- One earlier test run of the judge (51 calls on 3 fixture examples) cost about **$0.012** by the tool's own accounting. That run only proved the connection works; it measured nothing about quality.
- The cap is the tool's own accounting, not a bill limit. It does not include what your own app spends. Set a limit in your OpenAI account too.
- With `--live`, the question, your app's answer, the retrieved passages, and for some scores the reference answer are sent to OpenAI. [skill/references/disclosures.md](skill/references/disclosures.md) lists every network call.

## Words used here

- **Golden set:** the questions a person has checked, each with a reference answer and the exact passage that supports it.
- **Dev set / held-out set:** two parts of the golden set. You study the dev set. You use the held-out set once, at the end, so you cannot fool yourself.
- **Judge:** a language model that grades answers. It can be wrong, which is why its scores come with repeats and spread.
- **Retrieval mode:** how the app looked things up. `lexical` here means matching source names, which is free and offline. `semantic` means meaning-based scoring with the paid judge.
- **Fingerprint (hash):** a short code worked out from a file. If the file changes, the code changes. The tool uses fingerprints to be sure the questions and documents did not change between runs.
- **Baseline:** the run of your app before the change. You compare the "after" run against it.
- **Latency, p50 and p95:** how long the app took to answer. p50 is the typical answer. p95 is the slow end: 95 of 100 answers were at least this fast.
- **Error rate / invalid rate:** the share of questions where the app failed or timed out, and the share of answers the tool could not use.

## How we check the checker

Planned, not built yet:

1. **Negative controls:** feed the scorer deliberately wrong answers and empty passages, and confirm the scores drop.
2. **Judge agreement:** compare the judge's verdicts with a person's own labels on a sample.

Built: **repeat spread.** The judge scores each question several times (`--repeats`, default 3, up to 5) and the spread is reported. It is tested offline with a fake judge. It has not been measured on a real system.

The tool also records which version of itself produced every run (`evaluator_revision` in the run file). Do not change the scoring code between a baseline and the run you compare it with. If you do, run the baseline again.

## Status

Last checked: 2026-11-22.

**VERIFIED** (commands run and passing, on Windows):
- 206 automated tests pass, on Python 3.12 and on 3.14, with no network and no paid calls. They include the offline workflow against a local fake app: import, approval, freeze, `ragkit run` with resume and refusals, request templates, `ragkit init`, the speed, error and cost measurements, and the readable and `--json` output.
- `ragkit doctor`, `ragkit smoke` and `ragkit corpus inspect benchmarks/fastapi-docs` run. The package builds, and the wheel includes the agent skill and no test files.
- **Install from GitHub (2026-11-22):** the exact `uv tool install` command in the quick start, run against the default branch in a fresh environment, installed the tool. `ragkit smoke`, `ragkit doctor`, `ragkit init` and the skill copy all worked, and the run file recorded the merged commit `6180df5`.
- **GitHub's automatic checks (2026-11-22):** on the merge commit `6180df5`, all five checks passed: Ubuntu and Windows, each on Python 3.12 and 3.14, plus the job-application-kit tests.
- A real judge call worked once, on 2026-11-21: `gpt-4.1-mini`, 3 fixture examples, about $0.012. This showed compatibility only, not quality.
- **A real app, in a throwaway test (2026-11-22):** the tool ran against the real Conversational Agent Builder at tag `baseline-v1` (a clean checkout, in keyword-only mode with no key). Four unreviewed questions were answered with none failing. The answer, retrieved passages and source IDs were captured, and `evaluate` and `report` ran. This proves the plumbing. It is not a result and is not used in the case study. Steps and findings are in [docs/RUNBOOK_BUILDER.md](docs/RUNBOOK_BUILDER.md). It showed two gaps: per-question latency was not recorded, and refusing to answer cannot be assessed in keyword mode. Latency recording has since been added (see the next list: UNVERIFIED against the real Builder).

**UNVERIFIED:**
- The Builder in **meaning-based (semantic) mode**. That needs an OpenAI key set for the Builder, which was not available for the test.
- `ragkit run` and `ragkit adapter test` against the Builder or any real app. They were tried only against the local fake app. The real-app test above used `predict`, `evaluate` and `report` by hand.
- `dataset import` and `corpus init` on a real project. They are covered by automated tests only.
- How the readable output looks in every terminal. Its plain-text form was checked in Git Bash and PowerShell on Windows, and the plain `[ok]` fallback for terminals without checkmarks is tested. Colours depend on your terminal, and `NO_COLOR` turns them off.
- The new speed, error and cost measurements (latency, token counts, app-reported timing, error rate, `thresholds.yaml` ceilings) and the document-level retrieval scores. They are covered by automated tests with fake apps. They have not been run against the real Builder or any real app, and the real Builder's token and timing fields are read from its source code, not from a live response.
- Judge scoring of a real app: no real before-and-after run has been done.

**Not built:** negative controls, judge agreement, question generation from your own documents, wildcard response paths.

**The first case study** will use the [Conversational Agent Builder](https://github.com/cliffordnwanna/CONVERSATIONAL_AGENT_BUILDER) at tag `baseline-v2` (commit `2af15d8`). **The tag exists; no evaluation run yet, and no results exist.** It adds per-turn timing and split prompt and completion token counts to the chat response. This tool's Builder adapter does not read those new fields yet, so the Builder's token cost still shows as unavailable until it does, and that has not been tried against a live response. The earlier real-app test used the existing tag `baseline-v1`. Steps: [docs/RUNBOOK_BUILDER.md](docs/RUNBOOK_BUILDER.md).

## Limits

- About 20 held-out questions give wide ranges of doubt. Treat results as a strong hint, not proof.
- A judge model can be wrong and can share the blind spots of the app it grades.
- Reference answers are written by a person. A mistake there changes every score.
- Text RAG only. Documents are limited to 20 files and 100,000 characters in total.

## The agent skill

The [`skill/`](skill/) folder teaches an AI coding agent to drive `ragkit` for you, with the same rules: a person approves the questions, nothing paid runs without your yes, and no results are claimed that were not produced. It is optional. Run `ragkit init` to copy it (it asks first), or copy the folder yourself into your agent's skills folder as `rag-eval-kit`. It is v0.1: written from the code and the offline tests, and not yet tried in a real agent session.

## Development

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest      # offline; only loopback network is allowed
```

CI makes no paid calls and uses no secrets. Licensed under Apache-2.0. No employer or client data is included. The benchmark corpus is MIT-licensed FastAPI documentation, with its source recorded in `benchmarks/fastapi-docs/provenance.json`.
