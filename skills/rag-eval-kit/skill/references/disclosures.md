# Disclosures: network, cost and data

Read this before running anything. It describes what `ragkit` does when run from this skill's workflow. It was written from the source and the offline test suite; it was not independently audited, and your environment (proxy settings, dependencies) can differ.

## What makes no network call

`doctor`, `init`, `plan`, `corpus init`, `corpus inspect`, `dataset generate`, `dataset import`, `dataset review`, `dataset freeze`, `evaluate --retrieval-mode lexical`, `compare`, `report`. (`init` writes files and, only if you say yes, copies the skill. `corpus init` and `dataset import` only read and write local files.) `smoke` starts a mock server on the local machine (loopback only) and calls it; it makes no paid calls. The repository's tests allow only loopback network.

`doctor` says it did not check the network (`provider_connectivity: UNVERIFIED` with `--json`): it does not check the internet or any provider.

## What calls your own RAG application

`ragkit adapter test` sends **one** question to the endpoint in `adapter.json` and prints what it read from the answer. It saves nothing. `ragkit run` calls `predict` for every question in the dataset split you chose, then scores locally. Both contact your app, never OpenAI.

`predict` sends every question in the dataset to the target application you configure (the generic HTTP adapter or the Builder adapter). Questions and any headers you configure leave the machine for that URL. With the Builder adapter, each question creates a session, ingests the corpus, asks once, captures the answer, and deletes the session. Use a target you trust with the dataset. Auth headers should use `${ENV:NAME}` placeholders so secrets stay in environment variables.

## What calls OpenAI (paid, opt-in)

Only `evaluate --live --approve-paid` (semantic mode) and `spike --live` call a paid API. They call `https://api.openai.com/v1` chat completions through DeepEval with the judge model named in your config file. Each call is reserved against a per-run budget first. The default budget is zero, which blocks paid calls.

**Data sent:** the judge prompts are built by DeepEval from the case fields the metrics need: the question, the application's answer, the retrieved contexts, and, for some metrics, the reference answer and evidence. Assume all of these can be sent. The bundled benchmark corpus is public MIT-licensed documentation. If you evaluate your own corpus or private questions with `--live`, that content goes to OpenAI under your account's terms. `spike --live` additionally runs DeepEval's Synthesizer, which also sends data.

**Key:** set `RAGKIT_OPENAI_API_KEY` in the environment. The CLI does not auto-load `.env` files. Never paste the key into chat or a file that is committed. Use a separate, spend-limited OpenAI project for judging if you can.

## What costs money

- The judge calls above, at the prices you put in the config file. The example config records a price source and a check date; prices change, so re-check them before relying on the figure.
- The cost guard is local accounting: it reserves cost per call from configured prices and reported token usage. It is not a provider billing cap and does not include your target application's own generation or embedding costs. Unknown usage is reported as unknown and blocks further calls.
- `ragkit plan` estimates a judge-only allowance from explicit rates, with no API calls. Show the estimate and the cap to the user before any paid run.

## Telemetry and local state

Before importing DeepEval the CLI sets DeepEval's telemetry opt-out and disables its dotenv loading, legacy key file and automatic tracing. This covers DeepEval only; transitive dependencies were not audited.

Files written locally: prediction JSONL files, run JSON files, report Markdown, and frozen dataset directories. Run and prediction files contain questions, answers and retrieved contexts. Treat them as sensitive if your data is. Keep `.env` and `runs/` out of version control.

## What this skill itself does

The skill is instructions. It does not send anything anywhere beyond the commands the user approves.
