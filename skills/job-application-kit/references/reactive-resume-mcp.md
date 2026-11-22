# Reactive Resume MCP (optional: documents and tracker)

Optional. If the user has not connected it, use `documents-without-rr.md` instead and do not ask them to set it up.

Address: `https://rxresu.me/mcp` (hosted) or your own instance plus `/mcp`. The user signs in with OAuth from their client. Each person uses **their own** Reactive Resume account. Never use or ask for someone else's key.

Use Reactive Resume only to **render documents and track applications**. Do the thinking and writing yourself. Do **not** use its AI tools (`tailor_resume_for_application`, `score_application_match`, `draft_application_message`, `autofill_application_from_job`): they need the user's own AI provider and bypass this skill's truth rule.

## Recipe

1. **Check for duplicates.** `list_resumes` and `list_applications`. Reuse nothing silently. Name new items `<Company> - <Role> - <YYYY-MM-DD>`.
2. **Create the resume.** `create_resume` with that name.
3. **Fill it with one patch.** First read the schema resource `resume://_meta/schema` and call `read_resume` so you copy the real structure. Then `apply_resume_patch` once:
   - **Overwrite all of `/basics`** so the account defaults (name, email, phone, location from the user's Reactive Resume account) never leak into a real CV. Set only the fields allowed in `private/preferences.md`; blank the rest.
   - Observed once in manual use (not reproducible, so treat as hints): each **experience item** may need `period` (an empty string was accepted when `dates` was set); each **skill item** may need `icon` and `proficiency`. The tool's own description did not mention these. Always trust the schema resource and the error message over this note.
   - If the patch fails validation, read the error, add the missing fields, and retry once. Then `read_resume` to confirm the content.
4. **Create the cover letter.** `create_cover_letter` **with the `resumeId`** so it inherits the sender details and design. Put the approved text in at creation. If you need to change it later, read the letter first; a conflict error means re-read and retry.
5. **Create the application.** `create_application` with company, role, stage `saved`, the posting link in the notes, **and both `resumeId` and `coverLetterId`**. This links the documents. **Do not** call the separate link tools (`api_documents_link_application`, or linking via `update_cover_letter`): they errored or were unnecessary in one manual session (not reproducible).
6. **Get the PDF.** `download_resume_pdf` returns a signed link that **expires in 10 minutes**, and anyone with the link can download until then. Fetch and save the file immediately and give it to the user. Use `export_cover_letter` for the letter.
7. **Notes and follow-up.** Add the next action as a note with `add_application_note`, and set a follow-up date with `update_application` (read the application first; do not overwrite fields you did not mean to change).

## Stages

Create applications at `saved`. Move to `applied` only when the **user** says they have applied. Never submit anything. Moving to Applied saves a "sent version" of the resume and letter automatically.

## Safety

- **Ask before any delete.** Deleting a resume or letter moves it to Trash for 30 days; **deleting an application is permanent.** Never purge without an explicit instruction.
- Never put API keys, tokens or signed links into saved files, notes or the repository.
- Do not attach a PDF to the application unless the user wants a frozen copy of what was sent.
- If the server is unreachable or returns repeated errors, stop, say which step failed, and offer the document as a file instead.

## Optional

If the resume check (ATS review) tools are available, you may run them to catch formatting problems and fix what they flag. Treat the result as a hint, not proof of how a company's software will score the CV.
