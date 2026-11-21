# RAG Eval Kit — Continuity State

Last updated: 2026-11-21.

## Current stage

- **Stage 1 — Foundations: DONE.** Budget safeguards, offline validation and the bounded reuse study are complete. No paid calls were made.
- **Stage 2 — Real judge verification: DONE.** The user set a $2 run budget and requested a low-cost model. Current official GPT-4.1 mini pricing was recorded in the sample config; a real run completed successfully without exceeding the cap.
- **Stage 3 — Portable contract: IMPLEMENTED (2026-11-21 audit), PARTIAL verification.** JSONL, Builder HTTP and generic HTTP adapters plus evaluate/compare/report exist and pass 64 offline tests (commit b68d661). NOT yet run against the real Builder or a mock server end to end.
- **Stage 4 — Reviewed test data: PARTIAL.** Corpus (6 FastAPI docs, MIT, corpus hash 6ba3a83d...) and 60 candidates generated and validated offline; awaiting pre-screen and owner approval. Not frozen. CLI has no dataset/smoke/corpus subcommands yet (doctor, plan, spike, evaluate, compare, report only).
- Owner decisions 2026-11-21: untrack Builder venv/; $5 total dev-baseline cap; pre-screen then owner approves; mock-server test for generic adapter; Builder = Vercel keyless demo; evaluator = GitHub-installed CLI.
- Stages 4–8 are **NOT STARTED**. See section 19 of the master brief for scope and hard stops.
- Do not proceed to a paid call, Builder modification, push, deployment or publication without the applicable approval.

## Source of truth and decisions

- Master brief: `C:\Users\Clifford.nwanna\Dev\RAG_EVAL_KIT_BRIEF.md` (section 19 updated 2026-11-21).
- Eight stages and five hard stops in brief section 19 supersede its earlier phase/gate table.
- Product: a small, trustworthy workflow proving whether a RAG change helped; not a new metrics framework or a claim of unique methodology.
- Keep DeepEval unless the reuse findings establish a clear reason to change. JSONL file input first; HTTP adapters must produce the same record contract. Missing evidence makes faithfulness/context metrics unassessable.
- Keep evaluator, skill and benchmark in one repo. Text RAG only. No employer data or IP.
- Paired bootstrap intervals for score deltas; exact McNemar for paired pass/fail; Wilson only for a single pass rate. Small held-out results are exploratory; run judge metrics three times and report spread.
- Separate cohesive commits are preferred. No push, tag push, production deploy or public publication without Hard Stop E.

## Repository revisions

### Builder

Path: `C:\Users\Clifford.nwanna\Dev\CONVERSATIONAL_AGENT_BUILDER`

| Item | Verified value |
|---|---|
| Branch | `main` |
| Pre-baseline HEAD / local `origin/main` | `c8ed04c5f16a888ee48693538b1db3f71b247d01` |
| Final baseline commit | `fadf5b27a4da764bb6e160b5841d9fe1c138a439` |
| Annotated tag | `baseline-v0` |
| Baseline working tree | Clean at last verification |
| Relation to local `origin/main` | Ahead 3 commits; nothing pushed |
| Reviewed raw-file manifest | `5AE25B3A8A1F0AC07CB81B75A6F1B7243FEB90075EA6F45D2CF82D458FF06FB2` |
| Legacy tracked `venv/` | Retained, unchanged; 1,474 files |

The baseline was captured in three separate commits. The evaluator's Stage 1 did not modify the Builder. Recheck cleanliness and the tag before any later adapter run.

### Evaluator

Path: `C:\Users\Clifford.nwanna\Dev\rag-eval-kit`

- Branch: `main`.
- Foundation commit: `ade122734462ec406f05d0bbb92dbaaa47f8268c` (`chore: establish offline RAG evaluation foundations`).
- The reuse report and this continuity record are kept in a separate documentation commit.
- Python environment: existing `.venv`; dependency installation was not run during Stage 1.
- `uv` is not available on the current PowerShell PATH. Validation used the existing `.venv\Scripts` executables directly.
- Implemented package, CLI, pinned dependency files, Apache-2.0 license, CI, offline DeepEval compatibility fixtures, budget ledger, and tests are present.
- `docs/REUSE.md` records pinned revisions, licenses, findings, reuse boundaries and limitations.
- The project is not yet a full evaluator: JSONL/HTTP adapters, reviewed dataset, evaluation workflow, skill, case study and deployment remain future stages.
- The `.env` file is local-only and Git-ignored. Its key is never printed or recorded in state.
- The live judge spend limit can be set per run with `RAGKIT_BUDGET_USD` or `ragkit spike --budget-usd`; the command-line option overrides the environment. The default in `.env.example` is zero.

## Stage 1 verification evidence

Commands were run from PowerShell against the existing evaluator environment; no package installation or paid call occurred. In the commands below, `$base` was `C:\Users\Clifford.nwanna\Dev\rag-eval-kit`.

| Command | Result |
|---|---|
| `& "$base\.venv\Scripts\ruff.exe" format "$base\src\rag_eval_kit\budget.py" "$base\src\rag_eval_kit\judge.py" "$base\tests\test_budget.py" "$base\tests\test_judge.py"` | **PASS**; 1 file reformatted, then final check reported 2 files unchanged |
| `& "$base\.venv\Scripts\ruff.exe" check "$base"` | **PASS**; “All checks passed!” |
| `& "$base\.venv\Scripts\ruff.exe" format --check "$base"` | **PASS**; 19 files already formatted |
| `& "$base\.venv\Scripts\pytest.exe" -q "$base\tests"` | **PASS**; 35 passed |

Pytest emitted dependency deprecation warnings (606 DeepEval tracing warnings and a `pytest-asyncio` loop-scope warning); no test failures.

### Stage 2 — real judge compatibility

- **Run ID:** `76d54101-070c-4703-b157-0a98d96c57f8`
- **Command:** `python -m rag_eval_kit.cli spike --live --approve-paid --config docs/judge.example.json --output runs/stage2-live-2026-11-21.json --budget-usd 2` (executed from PowerShell after importing the ignored `.env` into that process; key not printed).
- **Judge:** `gpt-4.1-mini`; official pricing source `https://developers.openai.com/api/docs/pricing`, checked 2026-11-21, configured standard input `$0.40` / output `$1.60` per million tokens.
- **Budget:** requested `$2`; 100-call configured reservation ceiling `$0.9638400`; actual 51 calls recorded `$0.0119040`; budget was not exhausted; no unresolved usage.
- **Results:** all 15 live metric calls succeeded (3 examples each for Faithfulness, Answer Relevancy, Contextual Recall, Contextual Precision and Contextual Relevancy); Synthesizer returned 3 candidates. Input 21,564 tokens; output 2,049 tokens.
- **Interpretation:** real provider/framework compatibility verified only for this model/configuration and these fixtures. This is not a quality benchmark. Generated candidates are not user-reviewed or approved. Provider usage cost is calculated from reported token usage and configured pricing, not an account invoice.
- The ignored run report is `runs/stage2-live-2026-11-21.json`; it may contain fixture prompts and judge outputs. It is not committed.
- After adding per-run budget selection and the live run record, the offline test suite passed **38 tests**; Ruff lint passed and all 19 files passed formatting checks.
- `ragkit plan --config docs/judge.example.json --questions 3 --calls-per-question 16` made no calls and estimated 49 calls, a `$0.4722816` reservation ceiling for that plan, and a `$0.9638400` ceiling at the configured 100-call limit.

Budget behavior now verified in source and offline tests:

- Every external call reserves the maximum configured cost before it starts.
- An unknown usage response remains unverified, retains the reservation, reports `known_cost_usd: null`, and blocks later calls.
- Partial token usage is preserved on the per-call record, but aggregate token fields remain unknown.
- Verified response model and finish reason are recorded.
- Provider failures do not expose provider response text and do not trigger automatic retries.
- The ledger is a run-level guard, not a provider billing cap.

Reuse study:

- Shallow clones of ProofRAG, Vectara open-rag-eval and Giskard were created in `%TEMP%\rag-eval-kit-reuse-2026-11-18`.
- Verified HEADs: `ea688e309a73d155756bf1a33e2d07bf13bb5cfb`, `e05341bc19bbc2944a1e28634a6f98b32e7a3238`, and `bfda958b3eee42927f961b26e33254ece3d46884`.
- Inspected actual root license files: MIT, Apache-2.0, Apache-2.0.
- Source/test findings and reuse recommendations are documented in `docs/REUSE.md`; no upstream code was run, installed, imported or copied.
- The exact temporary clone directory was removed and verified absent.

## Costs, external actions and data

- Stage 1 paid judge/Builder API calls: **0**; Stage 2 made **51 judge API calls**, with ledger-estimated spend **$0.011904**.
- No packages were installed/upgraded. No Builder changes, push, deployment or publication.
- Copilot/model-platform usage costs are not measured here.
- No user API key is stored in this repository or requested in chat.
- Official live pricing and model availability are not yet verified for Stage 2.

## Open issues and next action

1. Begin Stage 3 with file-first JSONL contract and adapters. Keep every paid builder generation behind its own explicit approved rate/cost limit.
2. Keep `baseline-v0` immutable. Do not modify the Builder merely to simplify integration.
3. No golden set exists yet. The user must review candidates before freezing; never tune on held-out data.
4. The root folder `C:\Users\Clifford.nwanna\Dev` is not itself a Git repository. The master brief is edited in place and cannot be committed there without an intentional repository decision.

## Required resume checks

1. Read this file, the master brief and `docs/REUSE.md`.
2. Verify Builder `main` is clean and `baseline-v0^{}` is `fadf5b27a4da764bb6e160b5841d9fe1c138a439`.
3. Verify evaluator working-tree contents before staging; never use `git add -A`.
4. Stop at Hard Stop A before any paid request.
