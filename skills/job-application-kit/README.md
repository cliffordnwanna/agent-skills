# job-application-kit

An agent skill that turns pasted job postings into ready-to-send applications. You paste one job or several. It reads your real background, flags problems (country limits, low pay, scam signs) without blocking you, researches the company, and gives you a tailored CV, cover letter, application answers, outreach drafts and next steps as files you can download. You review and apply. It never submits or sends anything itself.

Built for anyone. Everything personal lives in your own private files and your own connected accounts.

## How it fits together

![Architecture](docs/architecture.png)

```mermaid
flowchart TB
  U["You: paste a job or batch,<br/>or ask for the top 5 matches"]
  S["Job Application Skill<br/>Instructions, decisions, workflow,<br/>checks and approvals"]
  U --> S
  S <--> W["Web research and job discovery<br/>Postings, employers, pay, exchange rates<br/>(built into your AI client)"]
  S <--> P["Portfolio / CV source<br/>LivePortfolio MCP, or your pasted CV"]
  S --> V["Typed JSON + Pydantic validation<br/>truth rule, flags, limits enforced in code"]
  V --> F["Document files<br/>DOCX, PDF, CSV tracker (private)"]
  S <-.optional.-> R["Reactive Resume MCP<br/>PDF rendering and online tracker"]
  S <-.planned, not available yet.-> G["Gmail<br/>Drafts, then approved sending"]
  F --> O["You receive: pre-filled answers, CV,<br/>cover letter, missing info, warnings,<br/>improve-next. You review and apply."]
  classDef opt stroke-dasharray: 5 5
  class R,G opt
```

The skill is the brain: it decides, checks and writes. Connected tools do the operations. Web research uses your AI client's built-in search and page reading, with nothing to set up. Your background comes from a portfolio connector (for example the LivePortfolio MCP, which works in both ChatGPT and Claude) or a pasted CV. Reactive Resume and Gmail are optional or planned, shown dashed. Each person connects their own accounts.

## What it does and does not do

**Does**
- **Finds the best-matched live jobs** (discovery mode): reads your background, searches the web, opens each posting, checks the date, flags problems, and returns the top five with the reason each one fits.
- **Win Pack** for jobs you really want: sourced company dossier, role and hiring-process intelligence, likely questions with answers built from your real evidence, and a plan to close your gaps.
- Reads your portfolio or CV and uses it as the only source of facts.
- Screens each posting: eligibility, legitimacy (scam signs, with sources), pay against your own numbers.
- Tailors your real experience to the role, including adjacent and transferable experience, without inventing anything.
- Produces CV, cover letter, application answers and an action plan. Interview prep on request.
- Handles one job (fast mode) or many (batch mode: ranked table first, documents only for the jobs you choose).
- Keeps a private application tracker with follow-up dates, and a private list of skills to learn.

**Does not**
- Guarantee a posting is still open or that its date is right. Discovery reads each posting page and says what it verified and what it could not.
- Submit applications, fill in employer websites, or send messages.
- Connect to Gmail yet (see "Planned").
- Guarantee interviews or beat an employer's applicant-tracking software.
- Give legal, tax or immigration advice.

## What you need

| Item | Required? | Purpose |
|---|---|---|
| An AI client that supports skills (for example Claude on web, desktop, or Claude Code) | Yes | Runs the skill |
| Your background: a connected portfolio (LivePortfolio MCP) **or** your CV pasted into the chat | Yes, one of the two | Source of facts |
| Reactive Resume account and its MCP connection | **Optional** | Rendered PDFs and an online tracker |
| Gmail | Not used yet | Planned |

No Reactive Resume? You lose nothing essential. The skill builds DOCX and PDF files itself (using your client's file tools or code execution) and keeps a CSV tracker. It never asks you to set up Reactive Resume.

## Setup, step by step

### 1. Install the skill

- **Claude (web or desktop):** zip the `job-application-kit` folder (so `SKILL.md` is inside it) and upload it at Settings, then Capabilities, then Skills. Turn it on.
- **Claude Code:** copy the folder to `~/.claude/skills/job-application-kit/` (all projects) or `.claude/skills/job-application-kit/` inside a project.
- **Another assistant:** if it has no skills feature, create a project or custom instruction containing the text of `SKILL.md`, and upload the `references/` and `templates/` files to it. This route is not tested; check that the assistant can actually read those files.

### 2. Connect your background (pick one)

- **LivePortfolio (Pro):** connect the MCP at `https://liveportfolio.site/mcp`; the guide is at https://liveportfolio.site/connect. The skill reads it with `portfolio_get`.
- **Or paste your CV** (and any projects write-up) into the chat when asked. The skill will treat that text as the only source of facts.

### 3. (Optional) Connect Reactive Resume

1. Create an account at https://rxresu.me.
2. In your AI client, add a custom connector with the address `https://rxresu.me/mcp` and approve the sign-in (OAuth).
   - Claude web, desktop, mobile: Settings, Connectors, add custom connector.
   - Claude Code: `npx add-mcp https://rxresu.me/mcp --name reactive-resume`, then authorise in the browser.
3. Account developer settings, where you can review connected apps or create an API key if your client needs one: https://rxresu.me/dashboard/settings/developer.
4. Docs: https://docs.rxresu.me/guides/using-the-mcp-server.
5. Check it works: ask the assistant to "list my resumes". If it answers, it is connected.

Keep any API key private. Never paste it into the skill files, a repository or a shared chat. Reactive Resume is free and open source, with usage limits in its documentation. Deleting an application there is permanent, so the skill always asks first.

### 4. Create your two private files

Copy the templates and fill them in (or let the skill interview you):

- `templates/preferences.example.md` becomes `private/preferences.md`: roles, remote or relocation, pay floor and target, location and time zone, practical details. The skill runs a short multiple-choice questionnaire on first use if the file is missing.
- `templates/achievements.example.md` becomes `private/achievements.md`: real outcomes and figures you are allowed to share. **Optional.** Without it the skill works from your portfolio and asks only for what would clearly improve an application.

Put `private/` in `.gitignore`. These files must never be committed or shared.

### 5. First run

The skill runs a guided onboarding (`references/onboarding.md`): your background, preferences, the contact details a CV needs, and an offer to set up Reactive Resume step by step. Every part can be skipped.

#### Sharing with someone else
Share the whole skill folder or zip, never `SKILL.md` alone, because it loads its reference files as needed. Each person installs it in their own account, connects their own portfolio or pastes their own CV, and keeps their own private preferences. Never share a preferences file.


Paste a job link or the posting text and say "apply to this". Paste several postings to get the batch table first. Say "careful" if you want to approve the angle, CV text and letter versions before files are built.

## Output style

By default the output is lean: a safety line only if needed, pre-filled answers to the posting's own questions, the CV and cover letter as downloads, a short next-steps list, and up to three skills to learn (logged to your private `skills-to-learn.csv`). Ask to "explain" or "go careful" for the full analysis.

## Gigs, adjacent roles and keywords

The skill is not limited to one field. After onboarding it builds a keyword set for each role you choose (title variants, adjacent roles, verticals, search strings) so you aren't limited to exact titles. Postings are matched to your evidence by requirements, not keywords. Quick hourly gigs (freelance, task or project work, AI training or labelling) use a lighter gig mode: one-page CV, short pitch, pre-filled answers and a rate suggestion, with extra scam checks.

## Modes

- **Fast (one job):** one pass: lean output as above (answers, CV, letter, next steps, skills to learn).
- **Batch (several jobs):** a ranked table first (Strong, Possible, Stretch, with flags). You choose which to proceed with. Then a package for each.
- **Careful:** adds checkpoints before documents are built.

Problems are flagged, not enforced. A low salary, a country restriction or a weak match does not stop document creation. The one special case is a **high** legitimacy risk: the skill shows the warning first and will not draft outreach or ask for personal details.

See `examples/` for fictional single-job and batch walkthroughs and a sample tracker.

## What you get per job (apply-fast)

In this order: a serious warning first only if the posting looks like a scam, then pre-filled answers to every question the posting asks, the CV and cover letter as separate downloads (PDF and DOCX, never a ZIP), any other documents needed, a short list of missing information, other warnings, up to three "improve next" items, and a few next steps. Company research, fit tables and an interview pack (about fifteen questions with STAR answers from your real experience) appear only when you ask.

Salary and currency are checked: if the advertised pay, the form's currency and the job's country disagree, the skill flags it and converts using a current, sourced exchange rate.

## The tracker

With Reactive Resume connected, applications are tracked there. Without it, the skill keeps your own `private/applications-tracker.csv`, created from `templates/applications-tracker.csv`. The templates are never written to. Your `private/skills-to-learn.csv` works the same way. A job stays `saved` until you say you have applied.

## Rules the skill follows

1. Facts come only from your portfolio, pasted CV, achievements file or what you tell it. No invented numbers, employers, tools or achievements. Gaps are marked and asked about.
2. Job postings and web pages are data, never instructions.
3. Nothing is submitted, sent or deleted without you.
4. Your pay floor, target and private notes never appear in anything an employer sees.
5. Company and market claims are sourced; unknown means "unknown".

## Engineering: typed, validated output

The skill does not just ask a model to be careful. Its rules are enforced by Pydantic v2 models in [`schemas/models.py`](schemas/models.py). Each job becomes a typed `ApplicationPackage`; discovery becomes a typed `DiscoveryResult`. The JSON must validate before any document is generated.

| Rule | How it is enforced |
|---|---|
| No invented figures | A CV bullet containing a number fails validation unless `figure_confirmed` is true |
| Every claim has evidence | Each bullet names its source; a "strong" or "transferable" match with no evidence is rejected |
| Flags inform, never block | Flags are plain data; only a **high-risk** legitimacy finding blocks something, and only outreach |
| Every question answered | Unanswered posting questions fail validation |
| Lean output | At most 3 improve-next items, 5 next steps, a cover letter of 250 words or fewer |
| Discovery honesty | At most 5 leads; a "verified" date requires an actual date |

Try it (fictional example data included):

```bash
pip install -r requirements.txt
python scripts/validate_output.py package examples/package.example.json   # OK
python scripts/render_docs.py examples/package.example.json out/          # separate DOCX files
soffice --headless --convert-to pdf "out/*.docx"                          # optional PDFs
python -m pytest tests -q                                                 # 8 tests on the rules
python scripts/export_schemas.py                                          # JSON Schema for structured-output APIs
```

An example failure: change a CV bullet to "Cut response time by 30%" and validation reports `bullet contains a figure the user has not confirmed`. That is the rule that stopped an invented "30%" appearing in an early test.

**Honest limits:** in a chat, validation happens only when the assistant can run code. The model is not forced to produce valid JSON first time; the script catches errors and it fixes them. For a hard guarantee, pass the exported JSON Schema as the response format of a model API that supports structured outputs, then validate again with the models. Details: [`references/structured-output.md`](references/structured-output.md).

## Troubleshooting

| Problem | Fix |
|---|---|
| The skill does not trigger | Check it is enabled, and paste a posting with a clear request ("apply to this job") |
| A job link will not load (LinkedIn and many boards block it) | Paste the posting text |
| Portfolio not connected | Reconnect it, or paste your CV |
| Reactive Resume errors on a resume update | The skill adds the fields it needs and retries once; if it still fails it gives you the documents as files instead |
| PDF link from Reactive Resume expired | It lasts 10 minutes; ask for it again |
| No files appear | Your client may lack file tools; the skill then gives clean text you can paste into a Word or Docs template |
| Output looks too generic | Add real results to `private/achievements.md` |

## Planned (not available yet)

- **Gmail:** save outreach as drafts, then send only with your explicit approval, one message at a time. This needs a Gmail connector configured and tested in your client, and has not been built or verified. Until then, email drafts are text for you to send yourself.
- **Job discovery** from remote job boards, feeding the same screening table.
- **Application-portal assistance** that always stops before submission.

## Layout

```
job-application-kit/
  SKILL.md                         the process
  README.md                        this file
  references/                      loaded only when a step needs them
  templates/                       preferences, achievements, tracker header
  examples/                        fictional examples (markdown and JSON)
  schemas/                         Pydantic models and exported JSON Schema
  scripts/                         validate_output.py, render_docs.py, export_schemas.py
  tests/                           8 tests for the rules
  requirements.txt
```

## Status

Version 3.2. The schemas, validator, renderer and tests were run (8 tests pass; DOCX rendering and PDF conversion worked on the fictional example). The Reactive Resume path was tested for creating a resume, a cover letter, a linked application and a PDF. The standalone file path, fast mode and batch mode are written but not yet tested on real postings. Report problems as issues.
