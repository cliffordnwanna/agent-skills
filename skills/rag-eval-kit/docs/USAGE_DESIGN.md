# Usage design (proposal, not built)

Status (2026-11-22): the first slice below was approved and built: `ragkit.yaml` with `ragkit run` through the lexical stages, `dataset import` (with a small `corpus init` helper it needs), the generic HTTP request template, `ragkit adapter test`, and `ragkit init`. Sections 1 and 2 describe the journey *before* that work. Not built: wildcard response paths (list indexes such as `choices.0.message.content` already worked), question generation from your own documents (v0.2), and the section 5 accuracy checks. Flags were read from the CLI source and `--help`.

## 1. Today's developer journey (verified)

All three paths start with `uv tool install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"` (the `pip install` form of that URL was tested via `git+file` only; the real GitHub install is untested) and need a reviewed, frozen dataset first.

**Dataset (all paths).** `ragkit corpus inspect <dir>`, then `ragkit dataset generate --corpus-dir <dir> --output-dir <new>`, human review of `review.csv`, `ragkit dataset review <csv> --corpus-dir <dir>`, `ragkit dataset freeze <csv> --corpus-dir <dir> --output-dir <new> --approved-by "<name>" [--seed N]`. Output: `golden.jsonl`, `dev.jsonl`, `heldout.jsonl`, `freeze.json`.

**A. File-based JSONL (any system).** Write one record per question to a JSONL file (fields: `question_id`, `question`, `answer`, `retrieved_contexts`, `retrieved_source_ids`, `target_revision`, `retrieval_mode`, plus reference fields). Then
`ragkit evaluate preds.jsonl --output run.json --target-revision <sha> --dataset-hash <h> --corpus-hash <h> --retrieval-mode lexical`
(add `--live --approve-paid --config judge.json --budget-usd N [--repeats 1-5]` with `--retrieval-mode semantic` for judge metrics), then `ragkit compare before.json after.json [--pass-metric M --pass-threshold T --bootstrap-samples N --seed N --allow-incompatible --output f]`, then `ragkit report run.json [--output f.md]`.

**B. Generic HTTP.** `ragkit predict dev.jsonl --adapter generic --adapter-config cfg.json --target-revision <sha> --output preds.jsonl [--concurrency 1-5]`, then the `evaluate` step above. `cfg.json` fields: `base_url`, `endpoint`, `question_field`, `question_id_field`, `answer_path`, `contexts_path`, `source_ids_path`, `retrieval_mode_path`, `abstained_path`, `headers` (`${ENV:NAME}` for secrets), `timeout_seconds`, `max_response_bytes`, `max_retries` (0-3), `retry_backoff_seconds`.

**C. Builder.** Same as B with `--adapter builder --adapter-config '{"base_url": "http://localhost:3000"}'` and optional `--semantic`, `--corpus-dir`.

## 2. Where it is hard to use today

1. **Hash plumbing.** `evaluate` needs `--target-revision`, `--dataset-hash`, `--corpus-hash` and `--retrieval-mode`, all of which already exist in `freeze.json` or the predictions. Users copy them by hand.
2. **No config file.** Every command repeats its flags; nothing remembers the endpoint, judge, budget or dataset.
3. **`dataset generate` only writes the built-in FastAPI candidate set.** A developer with their own corpus has no way to get candidates, so the "own project" journey does not exist yet. This is the biggest gap.
4. **Generic adapter is POST-JSON-with-one-field only.** No request template (extra fixed fields, nested bodies, query strings, other auth schemes), no multi-turn.
5. **No guided sequence.** The human gates (review, freeze, thresholds, paid-call approval) are enforced, but the user must know the order.
6. **Two-step paid safety is correct but verbose** (`--live`, `--approve-paid`, config, budget).

## 3. Proposal: `ragkit init`, `ragkit.yaml`, `ragkit run`

Modelled on promptfoo (init, edit config, eval, view) and Terminal-Bench (install once, one run command, a dataset listing). Those two are described from the reviewer's notes; I did not re-read their docs. Copy conventions, not code, and check licences before reusing any code.

```
uv tool install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"
ragkit smoke     # unchanged: zero-cost first run
ragkit init      # writes ragkit.yaml (+ optionally copies the skill into the agent's skills dir)
ragkit run       # runs the pipeline, stops at human gates, resumes
```

`ragkit.yaml` (all optional except `target` and `corpus`): `target` (adapter and its config or a path to it), `corpus.dir`, `dataset.dir` (the frozen one), `revision` (default: `git rev-parse HEAD` of the project), `judge` (config path), `budget_usd` (default 0), `thresholds` (path), `output.dir`.

`ragkit run` stages, in order, each skipped if its output exists and is valid: corpus inspect, candidates, **GATE: human review and freeze (prints what to do, exits 0, resumes next run)**, predict, evaluate (lexical), **GATE: thresholds file must exist before any run**, evaluate (semantic) only if `budget_usd > 0` and the user passes `--approve-paid` (never from the file), compare when a baseline run exists, report. State is the files already written (frozen dir, preds, run JSON); no hidden database. It reuses today's functions; nothing in the evaluation maths changes.

Smallest first slice: a `ragkit.yaml` loader that fills today's flags (removes pain points 1 and 2) plus `ragkit run` through the lexical stages. `init` and skill-copy come after.

## 4. Generic HTTP: request template and response paths

Keep today's config working. Add optional keys:
- `request` : a JSON template with `${question}` and `${question_id}` placeholders, e.g. `{"messages": [{"role": "user", "content": "${question}"}], "stream": false}`. If absent, use `question_field` as now.
- `method` (default POST), `query` (template for GET).
- Response mapping already exists as `answer_path`, `contexts_path`, `source_ids_path`; extend the path syntax to dotted and indexed forms (`choices.0.message.content`) and a wildcard for lists (`sources.*.id`). Check today's path syntax before specifying.
- Keep `max_response_bytes`, retries, timeouts, loopback-only tests. Add a `ragkit adapter test --adapter-config cfg.json` that sends one question and prints what was extracted, so users fix paths before a full run.

## 5. Proving the evaluator is right (reported in the case study)

1. **Negative controls (free, lexical + optional judge).** From the dev predictions, build three variants: shuffled answers across questions; empty `retrieved_contexts` and `retrieved_source_ids`; correct answers with wrong sources. Scores must drop clearly. Judge-metric controls cost money and need approval. Report each control's score next to the real run.
2. **Judge agreement.** The user labels a sample of dev answers (pass or fail) blind to judge scores; report agreement with the judge's pass/fail at the agreed threshold (raw agreement and Cohen's kappa) and list disagreements. Sample size is decided up front; with a small sample report it as exploratory.
3. **Repeat spread.** `--repeats 3` already exists; report the spread per metric.
4. **Same-system sanity run.** Compare a run to itself and to a repeat of itself: the difference should be about zero and not significant.

## 6. Time estimate (rough, one developer, excludes the human CSV review)

- `ragkit.yaml` loader and `run` through lexical stages, with tests: 1 to 1.5 days.
- Generic HTTP request template, path syntax and `adapter test`: 0.5 to 1 day.
- Candidate generation for a user's own corpus (design first, since it needs a model call or a rule-based method and has cost and quality questions): not estimated; needs its own proposal.
- Negative-control and agreement scripts and tests: 0.5 to 1 day.
- `init` and skill copy: 0.5 day.
- Docs and the video's command listing: 0.5 day.

Settle this design before the baseline run so the commands in the case study are the final ones. The dataset freeze is data only and does not depend on it.

## Decisions needed

1. Is the first slice (config loader plus `run` through lexical stages) the right size?
2. Should "your own corpus" candidates be in scope for v0.1, or is the first case study FastAPI-only and clearly labelled so?
3. Where should `ragkit.yaml` live (project root) and may `init` write the skill into the agent's skills directory (project or user level)?
