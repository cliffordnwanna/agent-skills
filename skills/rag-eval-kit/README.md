# RAG Eval Kit

A small, local workflow for answering one question honestly: **did this change make my RAG application better?**

It connects to a RAG app over HTTP (or reads a JSONL file), scores retrieval and answers against a human-reviewed question set, and compares two runs with paired statistics, recorded costs and a hard spending cap. It is a Python command-line tool installed from GitHub, not a hosted service.

It does not implement its own metrics: answer-quality scoring uses [DeepEval](https://github.com/confident-ai/deepeval). Scope is text RAG only.

## Status

| Area | State |
|---|---|
| CLI: `doctor`, `plan`, `spike`, `corpus inspect`, `dataset generate/review/freeze`, `predict`, `evaluate`, `compare`, `report`, `smoke` | Implemented; covered by 75 offline tests |
| Generic HTTP adapter (retries, timeouts, env-based auth headers) | Verified against a local mock server |
| Builder adapter | Verified once against a real local Conversational Agent Builder in live and offline modes |
| Judge metrics through DeepEval | Verified on 3 fixture examples with `gpt-4.1-mini` (compatibility only, not a benchmark) |
| Benchmark dataset | 60 candidates exist and are **not yet human-approved or frozen** |
| Agent skill (`skill/`) | v0.1: written from the code and offline tests; no live case study, not yet exercised in a real assistant session |
| Before/after case study | **Not yet run** |

## Install (Windows PowerShell)

This tool lives in the `agent-skills` monorepo, under `skills/rag-eval-kit`.

**Use it** (installs the `ragkit` command; needs Python 3.12 to 3.14):

```powershell
pip install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"
ragkit --help
```

**Develop or run the bundled benchmark** (the benchmark files are not part of the installed package, so clone):

```powershell
git clone https://github.com/cliffordnwanna/agent-skills.git
cd agent-skills/skills/rag-eval-kit
uv sync --locked          # needs Python 3.12+ and uv
uv run ragkit --help
```

**Agent skill (v0.1):** copy the `skill/` folder (it holds `SKILL.md` and `references/`) into your assistant's skills directory as `rag-eval-kit`. It does not need the tests or the source tree. Status: workflow verified offline; no live case study yet. Read `skill/references/disclosures.md` for network calls, costs and data sent.

## Try it with no API key and no cost

```powershell
uv run ragkit doctor      # local checks, no network
uv run ragkit smoke       # mock RAG server -> adapter -> retrieval metrics, 0 paid calls
uv run ragkit corpus inspect benchmarks/fastapi-docs
```

## Workflow

1. **Corpus.** `ragkit corpus inspect <dir>` verifies document hashes, licence and size limits against `provenance.json`.
2. **Candidates.** `ragkit dataset generate --corpus-dir benchmarks/fastapi-docs --output-dir <new dir>` writes candidate questions and `review.csv`. These are *unreviewed*.
3. **Human review.** Fill the `keep` column (`yes`/`no`) for every row and fix text as needed. `ragkit dataset review <csv> --corpus-dir ...` validates the sheet; blank rows are an error.
4. **Freeze.** `ragkit dataset freeze <csv> --corpus-dir ... --output-dir <new dir> --approved-by "<name>"` writes `golden.jsonl`, `dev.jsonl`, `heldout.jsonl` and `freeze.json` with SHA-256 hashes and the split seed. Cases that share evidence stay in the same split. Frozen directories are never overwritten. Use the held-out split once, at the end.
5. **Predict.** `ragkit predict dev.jsonl --adapter generic|builder --adapter-config cfg.json --target-revision <git sha> --output preds.jsonl`. Failed questions are listed and make the command exit non-zero; none are silently dropped.
6. **Evaluate.** `ragkit evaluate preds.jsonl ...` computes retrieval metrics offline (`--retrieval-mode lexical`), or judge metrics with `--retrieval-mode semantic --live --approve-paid --config docs/judge.example.json`.
7. **Compare and report.** `ragkit compare before.json after.json` then `ragkit report run.json`. Runs with different datasets, corpora, judges or retrieval modes are refused unless you override.

Run `ragkit <command> --help` for every option.

## Adapters

**Generic HTTP** (`adapter-config` JSON): `base_url`, `endpoint` (default `/api/chat`), `question_field`, `answer_path`, `contexts_path`, `source_ids_path`, `retrieval_mode_path`, optional `headers` (use `${ENV:NAME}` for secrets), `timeout_seconds`, `max_retries` (0-3). The target must return its retrieved context; without it, faithfulness and context metrics cannot be assessed and are reported as such rather than scored.

**Builder:** `{"base_url": "http://localhost:3000"}`. Each question uses a fresh session: ingest corpus, ask once, capture, delete. Semantic runs require the Builder to report `live` mode.

**JSONL:** any system can write predictions in the documented record shape (`question_id`, `question`, `answer`, `retrieved_contexts`, `retrieved_source_ids`, `target_revision`, `retrieval_mode`, ...) and use `evaluate` directly.

## Cost controls

Paid judge calls need `--live --approve-paid`, a config with explicit prices, and a budget from `RAGKIT_BUDGET_USD` or `--budget-usd`. The default is zero, which blocks paid calls. Each call reserves its maximum cost before it starts; unknown usage is reported as unknown and blocks further calls. This is a local per-run guard, not a provider billing cap. `ragkit plan` estimates cost without making calls.

Copy `.env.example` to `.env` and put your key in `RAGKIT_OPENAI_API_KEY`. The CLI does not auto-load `.env`; import it into the current process:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
```

## Statistics

Score differences use paired bootstrap confidence intervals; paired pass/fail changes use an exact McNemar test; a single pass rate uses a Wilson interval. A held-out set of about 20 questions supports exploratory conclusions only. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Development

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest             # offline; only loopback network is permitted
```

CI makes no paid calls and uses no secrets. Licensed under Apache-2.0. No employer or client data is included; the benchmark corpus is MIT-licensed FastAPI documentation with provenance in `benchmarks/fastapi-docs/provenance.json`.
