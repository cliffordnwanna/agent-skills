# job-application-kit

An agent skill that turns pasted job postings into ready-to-send applications. You paste one job or several. It reads your real background, flags problems (country limits, low pay, scam signs) without blocking you, and gives you a tailored CV, cover letter, application answers and next steps as files you can download. You review and apply. It never submits or sends anything itself.

**Why it exists:** most AI job-application tools invent achievements. This one is built around a truth rule (nothing in a CV that is not in your portfolio or your words), a flag-don't-block screening step, and a small typed validator that checks the structured output before any document is generated.

> **Status in one line:** the validator, renderer and tests run and pass. The skill's workflow (fast, batch, discovery, Win Pack and gig modes) has **not yet been tested on real job postings**. See [Status](#status) for exactly what was and was not run.

Built for anyone. Everything personal lives in your own private files and your own connected accounts. This repository contains no personal data.

## How it fits together

![Architecture](docs/architecture.png)

```mermaid
flowchart TB
  U["You: paste a job or batch,<br/>or ask for the top 5 matches"]
  S["Job Application Skill<br/>Instructions, decisions, workflow,<br/>checks and approvals"]
  U --> S
  S <--> W["Web research and job discovery<br/>Postings, employers, pay, exchange rates<br/>(built into your AI client)"]
  S <--> P["Portfolio / CV source<br/>LivePortfolio MCP, or your pasted CV"]
  S --> V["Typed JSON + Pydantic validation<br/>truth rule, flags, limits checked in code"]
  V --> F["Document files<br/>DOCX, PDF, CSV tracker (private)"]
  S <-.optional.-> R["Reactive Resume MCP<br/>PDF rendering and online tracker"]
  S <-.planned, not available yet.-> G["Gmail<br/>Drafts, then approved sending"]
  F --> O["You receive: pre-filled answers, CV,<br/>cover letter, missing info, warnings,<br/>improve-next. You review and apply."]
  classDef opt stroke-dasharray: 5 5
  class R,G opt
```

The skill is the brain: it decides, checks and writes. Connected tools do the operations. Web research uses your AI client's built-in search and page reading. Your background comes from a portfolio connector (for example the LivePortfolio MCP, which supports Claude and ChatGPT) or a pasted CV. Reactive Resume is optional and Gmail is planned, both shown dashed. Each person connects their own accounts. The Mermaid source is also in [`docs/architecture.mmd`](docs/architecture.mmd).

## What it does and does not do

**Designed to do** (instruction-level behaviour, see [Status](#status) for what is tested)
- **Discovery mode:** read your background, search the web, open each posting, check its date, flag problems, and return up to five best matches with the reason each fits.
- **Win Pack** for jobs you really want: sourced company dossier, role and hiring-process intelligence, likely questions with answers built from your real evidence, and a plan to close gaps.
- Read your portfolio or CV and use it as the only source of facts.
- Screen each posting: eligibility, legitimacy (scam signs, with sources), pay against your own numbers.
- Tailor your real experience to the role, including adjacent and transferable experience, without inventing anything.
- Produce a CV, cover letter, application answers and an action plan. Interview prep on request.
- Handle one job (fast mode) or many (batch mode: a ranked table first, documents only for the jobs you choose).
- Keep a private application tracker and a private list of skills to learn.

**Does not**
- Guarantee a posting is still open or that its date is right. Discovery says what it verified and what it could not.
- Submit applications, fill in employer websites, or send messages.
- Connect to Gmail (planned, not built).
- Guarantee interviews or beat an employer's applicant-tracking software.
- Give legal, tax or immigration advice.

## What you need

| Item | Required? | Purpose |
|---|---|---|
| An AI client that supports skills (for example Claude on web or desktop, or Claude Code) | Yes | Runs the skill |
| Your background: a connected portfolio (LivePortfolio MCP, Pro plan) **or** your CV pasted into the chat | Yes, one of the two | Source of facts |
| Python 3.10+ (tested on 3.14.6 only) and `requirements.txt` | Only to run the validator and renderer yourself | Typed validation, DOCX rendering |
| Reactive Resume account and its MCP connection | **Optional** | Rendered PDFs and an online tracker |
| Gmail | Not used | Planned |

No Reactive Resume? You lose nothing essential. The skill builds DOCX files itself (using your client's file tools or code execution) and keeps a CSV tracker. It never asks you to set up Reactive Resume.

## Install

### 1. The skill

- **Claude (web or desktop):** zip the `job-application-kit` folder (so `SKILL.md` is inside it) and upload it at Settings, then Capabilities, then Skills. Turn it on.
- **Claude Code:** copy the folder to `~/.claude/skills/job-application-kit/` (all projects) or `.claude/skills/job-application-kit/` inside a project.
- **ChatGPT or other assistants:** not tested. If the assistant has no skills feature, create a project or custom instruction containing the text of `SKILL.md`, and upload the `references/` and `templates/` files to it. Check that the assistant can actually read them.

### 2. Your background (pick one)

- **LivePortfolio (Pro):** add `https://liveportfolio.site/mcp` as a connector; guide: https://liveportfolio.site/connect. The skill reads it with the `portfolio_get` tool (a read-only tool documented in the LivePortfolio MCP repository's `docs/tools.md`).
- **Or paste your CV** (and any projects write-up) when asked. That text becomes the only source of facts.

### 3. Optional: Reactive Resume

1. Create an account at https://rxresu.me.
2. Add the server address `https://rxresu.me/mcp` and approve the sign-in (OAuth is the recommended method in its docs).
   - Claude web or desktop: Settings, Connectors, add custom connector.
   - Claude Code: `npx add-mcp https://rxresu.me/mcp --name reactive-resume -a claude-code -g`, then run `/mcp` inside Claude Code and choose `reactive-resume` to sign in.
3. Docs: https://docs.rxresu.me/guides/using-the-mcp-server. The docs say the MCP address is shown under Settings, then Developer, in your account (https://rxresu.me/dashboard/settings/developer; that page needs you to be signed in, so its contents were not checked).
4. Check it works: ask the assistant to "list my resumes".

Keep any API key private; never paste it into the skill files, a repository or a shared chat. Deleting an application in Reactive Resume is permanent, so the skill always asks first. The Reactive Resume path was exercised manually once in the author's account; it is not reproducible from this repository and is not covered by tests.

### 4. Your private files

Copy the templates and fill them in (or let the skill interview you):

- `templates/preferences.example.md` becomes `private/preferences.md`: roles, remote or relocation, pay floor and target, location and time zone.
- `templates/achievements.example.md` becomes `private/achievements.md`: real outcomes and figures you are allowed to share. Optional.

`private/` is a folder in **your own workspace**, not inside this repository. If you keep your files in a git repository, ignore at least:

```
private/
__pycache__/
.pytest_cache/
out/
.env
```

These files must never be committed or shared. Never share a preferences file.

### 5. First run

The skill runs a guided onboarding (`references/onboarding.md`): your background, preferences, the contact details a CV needs, and an offer to set up Reactive Resume. Every part can be skipped. Then paste a job link or the posting text and say "apply to this". Paste several postings to get the batch table first. Say "careful" to approve the angle, CV text and letter versions before files are built.

To share the skill with someone else, share the whole folder or zip, never `SKILL.md` alone.

## Modes

- **Fast (one job):** one pass: answers, CV, letter, next steps, skills to learn.
- **Batch (several jobs):** a ranked table first (Strong, Possible, Stretch, with flags). You choose which to proceed with.
- **Careful:** adds checkpoints before documents are built.
- **Discovery, Win Pack, gig:** see `SKILL.md` and `references/`.

Problems are flagged, not enforced: a low salary, a country restriction or a weak match does not stop document creation. The one special case is a **high** legitimacy risk: the skill shows the warning first and will not draft outreach or ask for personal details. In code, only the outreach part is enforced (see below).

See `examples/` for fictional single-job and batch walkthroughs and a sample tracker.

## Typed, validated output

The skill's rules are also expressed as Pydantic v2 models in [`schemas/models.py`](schemas/models.py). Each job becomes an `ApplicationPackage`; discovery becomes a `DiscoveryResult`. The JSON should validate before any document is generated.

| Rule | What the code actually checks |
|---|---|
| No invented figures | A CV bullet containing a digit or a common number word ("percent", "half", "doubled", "thirty", ...) fails unless `figure_confirmed` is true. **This is a heuristic.** It misses quantities such as "one third", and `figure_confirmed` is set by whoever builds the JSON. |
| Every claim has evidence | Each bullet needs a non-empty `evidence` string; a "strong" or "transferable" match with no evidence is rejected. The code cannot check that the evidence is true. |
| Flags inform, never block | Flags are plain data. Only a `high_risk` legitimacy flag has an effect: it forbids the `outreach` field. Asking for personal details is an instruction, not a code check. |
| Every question answered | Posting questions with no matching answer fail validation (matched by exact text, ignoring case and spacing). |
| Lean output | At most 3 improve-next items, 5 next steps, and a cover letter of 250 words or fewer. |
| Discovery honesty | At most 5 leads; `date_verified` requires a `posted_date`. |

Commands (run from `skills/job-application-kit/`):

```bash
pip install -r requirements.txt
python scripts/validate_output.py package examples/package.example.json
python scripts/validate_output.py discovery examples/discovery.example.json
python scripts/render_docs.py examples/package.example.json out/            # separate dated DOCX files
python scripts/render_docs.py examples/package.example.json out/ --pdf      # also PDF if LibreOffice (soffice) is installed
python scripts/export_schemas.py                                            # refresh the JSON Schema files
python -m pytest tests -q
```

Rendered files are named `<Company> - <Role> - <YYYY-MM-DD> - <Document>.docx`, with characters that are illegal in file names removed. If `--pdf` is given and LibreOffice is missing, the script prints a notice and still writes the DOCX files.

An example failure: change a CV bullet to "Cut response time by 30%." and validation reports `bullet contains a figure the user has not confirmed`.

**Honest limits:** in a chat, validation happens only when the assistant can run code, and nothing forces the model to produce valid JSON first time. For a hard guarantee, pass the exported JSON Schema as the response format of a model API that supports structured outputs, then validate again with the models. Details: [`references/structured-output.md`](references/structured-output.md).

## Privacy model

- This repository contains generic rules, templates and fictional examples only.
- Your preferences (pay floor and target, relocation goals), achievements and trackers live in `private/` in your own workspace, never in the skill and never in a public repository.
- Your pay floor and target never appear in anything an employer sees.
- Postings, web pages and portfolio text are treated as data, never as instructions.
- Nothing is submitted, sent or deleted without you. Signed links and API keys never go into files.
- Details: [`references/privacy-and-security.md`](references/privacy-and-security.md).

## Limitations

- Not yet tested on real job postings, on ChatGPT, or in other clients.
- The truth rule depends on the model following instructions; the validator catches some violations, not all.
- Scam and eligibility screening can find red flags but cannot prove a job is safe.
- Web research quality depends on your client's search tools. Many job boards block automated page reads; you may need to paste the posting.
- PDF output needs LibreOffice or your client's own document tools.

## Design decisions

- **Truth rule, checked in code where possible.** A written rule is easy to forget under pressure, so the most checkable parts (figures need confirmation, claims need evidence) are also validator rules. It is a safety net, not a guarantee, and says so.
- **Flag, don't block.** The user has already read the job. Warnings (country, pay, timezone) inform the decision and never stop the work. The single exception is high scam risk, where no outreach is drafted.
- **Optional integrations.** Reactive Resume is optional and never required; the standalone file path is a full path. Gmail is not assumed to exist.
- **Private data separation.** Anything personal is read from your portfolio at run time or kept in your own `private/` files. The public repository stays generic.
- **Never submit.** The skill produces drafts. A person reviews and sends.

## Troubleshooting

| Problem | Fix |
|---|---|
| The skill does not trigger | Check it is enabled, and paste a posting with a clear request ("apply to this job") |
| A job link will not load (LinkedIn and many boards block it) | Paste the posting text |
| Portfolio not connected | Reconnect it, or paste your CV |
| Reactive Resume errors on a resume update | The skill reads the error, adds the fields it needs, and retries once; if it still fails it gives you the documents as files |
| PDF link from Reactive Resume expired | It lasts 10 minutes; ask for it again |
| No files appear | Your client may lack file tools; the skill then gives clean text you can paste into a Word or Docs template |
| Output looks too generic | Add real results to `private/achievements.md` |

## Status

Last checked: 2026-11-22, on Windows with Python 3.14.6.

**Tested (commands run and passing)**
- `python -m pytest tests -q`: schema and rule tests, number-word rejection, limits, file naming, the missing-LibreOffice notice, and a check that the exported JSON Schema files match the models.
- `python scripts/validate_output.py package` and `discovery` on the fictional examples.
- `python scripts/render_docs.py` on the fictional example: three separate DOCX files written and reopened with python-docx.
- Reactive Resume documentation check: the MCP address, the docs page and the tool names this skill references exist (read from the docs; no live call).
- LivePortfolio: the `portfolio_get` tool name and its read-only behaviour match the MCP repository's `docs/tools.md`.

**Implemented but untested**
- PDF conversion (`--pdf`): it worked in the author's environment, but was not run in the audit environment (no LibreOffice there). Only the "LibreOffice missing" notice is tested.
- Fast, batch, discovery, Win Pack and gig modes, and every step that needs a live model run: written as instructions, **not yet tested on real job postings**.
- The standalone file path and the tracker and skills-to-learn CSV logic: instruction-level only; no code writes those files.
- Reactive Resume path (resume, cover letter, linked application, PDF): exercised manually once in the author's account; not reproducible from this repository.
- Use in ChatGPT or any client other than Claude: not tested.

**Planned**
- Gmail: save outreach as drafts, then send only with explicit approval, one message at a time. Not built.
- Application-portal and form assistance that always stops before submission. Not built.
- Scripted discovery from job boards. Discovery today is instructions that use your client's web tools.
- A CI status badge, once the workflow in `.github/workflows/` has run green.

## Layout

```
job-application-kit/
  SKILL.md                         the process
  README.md                        this file
  docs/                            architecture diagram (png and Mermaid source)
  references/                      loaded only when a step needs them
  templates/                       preferences, achievements, tracker headers
  examples/                        fictional examples (markdown and JSON)
  schemas/                         Pydantic models and exported JSON Schema
  scripts/                         validate_output.py, render_docs.py, export_schemas.py
  tests/                           pytest tests for the rules and the renderer
  requirements.txt
```
