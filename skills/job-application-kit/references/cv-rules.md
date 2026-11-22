# CV rules

## Truth rule (applies first)

Every line comes from the portfolio, the user's pasted CV, or the user in this chat. Do not invent bullets, numbers, titles, employers, tools, dates or achievements. If a bullet would be stronger with a figure that you do not have, write `[needs your real figure]` and ask. Language models can produce plausible but invented metrics when asked for a strong bullet; this rule exists to stop that. The validator (`schemas/models.py`) catches digits and common number words, but it is a heuristic: you are the first line of defence.

## What you may change

- **Order and emphasis**: lead with the experience that matches the chosen angle.
- **Wording**: tighten and use the posting's terms **only where they are true** for the user. If the posting says "LLMOps" and the user did the work but called it something else, use the posting's word. If they did not do it, do not claim it; list it as a gap.
- **Length**: one page for under about ten years of experience, two pages at most.
- **Selection**: drop or shrink roles and projects that do not help this application.

## What you may not change

Employers, titles, dates, degrees, certifications, links, or anything that sounds like a measurement. Do not round or inflate figures.

## Employer-confidential work

If the portfolio describes work at an employer, describe it at capability level (what was built, with which technology) unless the user confirms a figure is cleared for public use. Do not name internal systems, customer data, internal metrics or architecture unless the user confirms it is allowed.

## Format (ATS-friendly)

- Single column, standard section names (Experience, Education, Skills, Projects, Certifications).
- Plain text bullets starting with a strong verb, one to two lines each, three to five per role.
- No tables, text boxes, images, icons or photos in the text itself. Dates in a consistent format.
- A short summary of two or three lines at the top, specific to the role.
- Skills grouped and relevant; do not stuff keywords. Do not claim that any format "beats" an applicant-tracking system; you cannot know a company's software.

## Header

Show only what `private/preferences.md` allows. Default: name, email, city and country, portfolio link, LinkedIn. Never leave account defaults from Reactive Resume in the header (see `reactive-resume-mcp.md`).

## Before the PDF

In fast mode, build the file straight away and list any `[needs your real figure]` gaps under Missing information. Only in careful mode show the full CV text and wait for approval first.
