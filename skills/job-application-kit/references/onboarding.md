# First-run onboarding

Goal: get a new user working in a few minutes, with every part skippable. Ask all preference questions in one message (see `preferences-intake.md`) and let the user answer in one line; for the other setup parts, one short group at a time. Accept "skip" or "later" for anything, record it, and move on. Never make a setup step a condition for producing documents.

## 1. Where your background comes from

- If a portfolio connector (LivePortfolio MCP) responds, use it and summarise what you found in five lines: role, strongest projects, skills, what is missing for a strong CV. Ask the user to correct anything wrong.
- If not, ask the user to paste their CV and, optionally, a short list of projects. Say this is enough.
- If the portfolio lacks outcomes or contact details, say which, and ask only for what the first applications need. Never invent them.

## 2. Preferences and roles

Run `preferences-intake.md`: one message of lettered multiple-choice questions the user answers in one line. Then run `role-and-keyword-expansion.md` for each chosen role. If the user prefers, accept a pasted block of preferences instead. Save as `private/preferences.md` or, in a chat or project without file storage, keep it in the conversation and give the user the full text to paste into a new chat later. Tell them plainly where it is stored.

## 3. Details a CV needs

Name, email, city and country, portfolio link, LinkedIn (all optional except name and email). Phone and street address are hidden by default. These are question 8 of `preferences-intake.md`: if the user already answered it, do not ask again. Ask only for what the portfolio and that answer did not provide.

## 4. Documents: Reactive Resume or plain files

Explain in two lines and let the user choose:

- **Plain files (default):** you build DOCX and PDF files and a CSV tracker. Nothing to set up.
- **Reactive Resume (optional):** a free resume app that renders polished PDFs and tracks applications online. Setup takes about five minutes.

If the user wants Reactive Resume, walk through it one step at a time and check after each:

1. Create a free account at https://rxresu.me.
2. Add the connector in their AI client: address `https://rxresu.me/mcp`, approve the sign-in. In Claude: Settings, Connectors, add custom connector. In Claude Code: `npx add-mcp https://rxresu.me/mcp --name reactive-resume -a claude-code -g`, then run `/mcp` and choose reactive-resume to sign in (this is the command in the Reactive Resume docs). In ChatGPT the custom-connector steps are not verified for this skill: if the option is missing or unclear, say so and offer plain files.
3. Optional account settings and API keys: https://rxresu.me/dashboard/settings/developer. Never paste a key into the chat or a shared file.
4. Test: call `list_resumes`. If it returns a list (even an empty one), it works. If it errors, retry once, then offer plain files.

Record the choice as `documents: reactive_resume` or `documents: files`. If they say "skip", record `files`. They can switch any time by saying so.

## 5. Finish

Show the saved summary in five lines, remind them the preferences are private (pay numbers especially), and invite them to paste the first job or a batch.
