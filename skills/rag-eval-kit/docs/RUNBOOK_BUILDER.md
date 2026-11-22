# Runbook: evaluate the Conversational Agent Builder

Repository: [CONVERSATIONAL_AGENT_BUILDER](https://github.com/cliffordnwanna/CONVERSATIONAL_AGENT_BUILDER).

> **Which tag.** The plumbing proof below was run at the existing tag **`baseline-v1`** (commit `971461d`). The real case study will use **`baseline-v2`**, which **does not exist yet (UNVERIFIED)**. Wherever a step says `baseline-v1`, use `baseline-v2` for the real evaluation once it has been created and checked.

Copy-paste PowerShell steps. Last run: 2026-11-22, Windows, Python 3.12 inside the tool environment, Node 24. The Builder steps were run at `baseline-v1`. The `ragkit` steps were run before the speed and cost measurements were added; those additions are marked below.

Labels: **VERIFIED** = I ran it and it worked. **UNVERIFIED** = written from the tool's help, not run.

> The plumbing proof in steps 1 to 7 is **exploratory**. Its output is not a result and must never be used in the case study. The real evaluation (steps 8 to 12) cannot start until a person has reviewed and frozen the question set.

## What you need

| Need | For | Status |
|---|---|---|
| Python 3.12 to 3.14 and `uv` | the `ragkit` tool | VERIFIED |
| Node 22.13 or newer, npm | the Builder | VERIFIED (Node 24, npm 11) |
| git | the clean checkout and exact-version check | VERIFIED |
| `OPENAI_API_KEY` (user-level environment variable) | **only** if you want the Builder in semantic mode, set before `npm start` | UNVERIFIED (not set on the test machine) |
| `RAGKIT_OPENAI_API_KEY` | **only** for paid judge scoring (step 10) | UNVERIFIED |

Neither key is needed for steps 1 to 7. Without `OPENAI_API_KEY` the Builder runs in `demo` mode: keyword matching, no AI. Never paste a key into a file or chat; set it in Windows Settings, then open a new terminal.

## Steps

**1. Get a clean checkout at the tag** (VERIFIED). A separate folder, so your working copy is untouched.

```powershell
cd C:\dev\CONVERSATIONAL_AGENT_BUILDER
git worktree add ..\builder-baseline-v1 baseline-v1
```

**2. Install and build the Builder** (VERIFIED: `npm ci` 33 s, build succeeded).

```powershell
cd ..\builder-baseline-v1
npm ci
npm run build
```

**3. Start it** in its own terminal window and leave it running (VERIFIED: ready in under a second).

```powershell
cd C:\dev\builder-baseline-v1
npm start
```

**4. Health check** (VERIFIED). Expect `"mode":"demo"` with no key, or `"mode":"live"` with a key.

```powershell
Invoke-RestMethod http://localhost:3000/api/health
```

**5. Install `ragkit`** (UNVERIFIED from GitHub; VERIFIED from a local copy of the branch).

```powershell
uv tool install "git+https://github.com/cliffordnwanna/agent-skills#subdirectory=skills/rag-eval-kit"
```

**6. Free checks** (VERIFIED). `doctor` also proves the Builder checkout is the exact tagged commit with no changes.

```powershell
ragkit smoke
$sha = git -C C:\dev\builder-baseline-v1 rev-parse HEAD
ragkit doctor --builder C:\dev\builder-baseline-v1 --target-revision $sha
```

**7. Exploratory plumbing proof** (VERIFIED). Four unreviewed questions, one per kind, against the running Builder. No judge, no key, no cost. Run from a clone of the repository (the benchmark files are not in the installed package).

```powershell
$corpus = "C:\path\to\agent-skills\skills\rag-eval-kit\benchmarks\fastapi-docs"
'{"base_url": "http://localhost:3000"}' | Set-Content builder.json
# EXPLORATORY-questions.jsonl: 4 lines copied from candidates\candidate_questions.jsonl
ragkit predict EXPLORATORY-questions.jsonl --adapter builder --adapter-config builder.json `
  --target-revision $sha --output EXPLORATORY-predictions.jsonl --corpus-dir $corpus
$c = ragkit corpus inspect $corpus | ConvertFrom-Json
$d = (Get-FileHash EXPLORATORY-questions.jsonl -Algorithm SHA256).Hash.ToLower()
ragkit evaluate EXPLORATORY-predictions.jsonl --output EXPLORATORY-run.json --target-revision $sha `
  --dataset-hash $d --corpus-hash $c.corpus_sha256 --retrieval-mode lexical `
  --target-repo C:\dev\builder-baseline-v1
ragkit report EXPLORATORY-run.json --output EXPLORATORY-report.md
```

What this showed (exploratory, 4 questions, keyword mode):

| Thing checked | Result |
|---|---|
| 4 of 4 questions answered, none failed | yes, under one second in total |
| Each record has the answer, 3 retrieved passages, source IDs, `retrieval_mode`, the tested commit | yes. `retrieval_mode` was `lexical` because the Builder was in demo mode |
| The run file records which version of the evaluator produced it | yes (`evaluator_revision`, taken from the git install) |
| The corpus fingerprint matches the pinned one | yes (`6ba3a83d…`) |
| Per-question latency recorded | **not at the time of the test** (`latency_ms` was empty). It has since been added: the tool now times the chat call itself and reads the Builder's per-turn timing and token total. This is covered by tests with a fake Builder and is **UNVERIFIED against the real Builder** |
| Abstention (declining unanswerable questions) | **not assessable** in demo mode: the Builder always returns excerpts, so there is no abstention signal |
| Source IDs repeat (for example `body, body, body`) | the Builder returns chunks, so one document can fill all three slots. Worth knowing before reading `Hit@3` |
| Cost | the Builder marks usage cost as UNVERIFIED. It reports one token total, not input and output separately, so the tool cannot price it and reports cost as unavailable |
| Semantic mode (`--semantic`, meaning-based retrieval) | **UNVERIFIED**: needs `OPENAI_API_KEY` |

## The real evaluation (starts after the question review)

All UNVERIFIED until a frozen question set exists. Flags are copied from `--help`.

**8. Prepare the questions.** A person reviews `review_prescreen.csv` (write `yes` or `no` in `keep` on every row), then:

```powershell
ragkit dataset review review.csv --corpus-dir $corpus
ragkit dataset freeze review.csv --corpus-dir $corpus --output-dir frozen --approved-by "Your Name"
```

**9. Agree the pass rules before looking at any result** (primary metric, guard metrics, cost cap). Write them down.

**10. Dev baseline.** Either one command, with a `ragkit.yaml` containing `target.adapter: builder`, `target.config: builder.json`, `target.repo: ..\builder-baseline-v1`, `corpus`, `dataset: frozen` and an `output` folder outside the Builder repository (or git-ignored):

```powershell
ragkit run
```

or the same steps by hand: `ragkit predict frozen\dev.jsonl --adapter builder ...`, then `ragkit evaluate ...`. For the paid judge scoring, first `ragkit plan --config docs\judge.example.json`, then `evaluate ... --retrieval-mode semantic --live --approve-paid --config docs\judge.example.json --budget-usd 2`. This needs the Builder in live mode and your judge key. `ragkit run` itself has only been tested against a fake app, not against the Builder.

**11. Fix and re-run.** Make one fix in the Builder, commit it, tag it `after-fix-1`, check it out in a second worktree, and repeat step 10 against that tag.

**12. Compare once, on the held-out set.**

```powershell
ragkit run --split heldout --confirm-heldout     # for baseline-v2 (UNVERIFIED: not created yet) and for after-fix-1, in separate output folders
ragkit compare baseline-run.json after-run.json --pass-metric <metric> --pass-threshold <value>
ragkit report after-run.json --output report.md
```

Do not change scoring code between the baseline and the comparison. Each run records the evaluator's commit so a mismatch can be seen.

## Clean up

Stop the Builder (Ctrl+C in its window). Remove the extra checkout when finished: `git -C C:\dev\CONVERSATIONAL_AGENT_BUILDER worktree remove ..\builder-baseline-v1`.
