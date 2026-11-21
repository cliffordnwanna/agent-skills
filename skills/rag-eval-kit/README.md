# RAG Eval Kit

Independent, local RAG evaluation tooling. The current version provides offline checks and a bounded DeepEval compatibility spike; it is not yet a complete RAG evaluator. JSONL/HTTP adapters, corpus review, end-to-end evaluation and improvement reports remain future work.

## Setup (PowerShell)

```powershell
uv sync --locked
uv run ragkit --help
uv run ragkit doctor
uv run pytest
uv run ruff check .
```

Offline commands need no API key. Live judge calls use a separate OpenAI key and a user-selected per-run spending cap. The example judge config uses `gpt-4.1-mini`; verify current prices in the [official API pricing](https://developers.openai.com/api/docs/pricing) before a paid run.

### Configure a live judge run

Copy `.env.example` to `.env`, add your key locally, and set `RAGKIT_BUDGET_USD` to the maximum this run may reserve. `.env` is ignored by Git. Never paste keys into chat or commit them. The CLI intentionally does not auto-load dotenv files; import values into the current PowerShell process without printing them:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
    }
}
```

The CLI option can set or override the cap for one run:

```powershell
New-Item -ItemType Directory -Force runs | Out-Null
uv run ragkit spike --live --approve-paid `
  --config docs/judge.example.json `
  --output runs/stage2-live.json `
  --budget-usd 2
```

If `--budget-usd` is omitted, `RAGKIT_BUDGET_USD` is used (default is zero, which blocks paid calls). A run stops before a call if its reservation would exceed the chosen cap. This is a local per-run reservation guard, not an account-wide or provider billing limit; builder generation, embeddings and hosting costs are not included. Live calls incur provider charges and send judge prompts to OpenAI.

### Verified compatibility run

On 2026-11-21, a live compatibility check used `gpt-4.1-mini`, a $2 per-run reservation cap and three fixed examples. All 15 metric calls (five metrics × three examples) and the Synthesizer completed; three candidate examples were produced for review. The ledger recorded 51 paid judge requests, 21,564 input tokens, 2,049 output tokens and **$0.011904** estimated from provider-reported usage and the configured price. The $2 cap was not reached. This checks integration only: the examples are fixtures, their metrics are not a benchmark, and the synthesized candidates are not approved golden data.

See [STATE.md](STATE.md) for stage status, run ID, verification evidence and repository revisions. Licensed under Apache-2.0. No employer or client data is included.
