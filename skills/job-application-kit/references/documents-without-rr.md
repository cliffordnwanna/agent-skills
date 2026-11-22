# Documents without Reactive Resume

This is a complete path. Use it whenever Reactive Resume isn't connected, or the user prefers files.

## Choose the method by what the client can do

1. **Client has document skills or tools** (for example Claude's docx and pdf skills; other clients vary, so check): create the files with them. DOCX is the safest format for editing; PDF for sending.
2. **Code execution available:** run `python scripts/render_docs.py <package.json> <outdir> --pdf` (validates the package first, writes separate dated DOCX files, and converts to PDF if LibreOffice is installed; otherwise it prints a notice and the DOCX files still arrive). Or build a DOCX with `python-docx` or `docx` (Node) yourself, then convert to PDF with LibreOffice if present, or build the PDF with a PDF library (for example `reportlab`).
3. **No file tools at all:** give clean Markdown the user can paste into a Word or Google Docs template, and say so in one line.

Check what is available instead of assuming. Do not ask the user to install anything unless nothing else works.

## CV layout (ATS-safe)

- One column, A4 or Letter (match the employer's country; default A4 outside the US).
- Standard fonts (Calibri, Arial, Helvetica), 10 to 11 pt body, clear section headings: Summary, Experience, Projects, Skills, Education, Certifications.
- No tables, text boxes, images or icons for content. Real hyphen bullets or list styles. Consistent dates.
- Links as visible text (portfolio, LinkedIn, GitHub), not hidden behind icons.
- Header limited to what `private/preferences.md` allows (default: name, email, city and country, portfolio, LinkedIn).
- Content rules are in `cv-rules.md`. Truth rule applies in full.

## Cover letter layout

Plain business letter, one page, the user's name and contact line at the top, date, greeting by name if a verified name exists (otherwise "Hello <Company> hiring team"), body, sign-off.

## One file per document

Provide each document as its own downloadable file: CV (PDF and DOCX), cover letter (PDF and DOCX), application answers, tracker CSV. Never bundle documents into a ZIP archive. Give each file separately so it can be opened and downloaded on its own.

## After building

- Open or re-read the file to check: no placeholder text left (other than marked `[needs your real figure]` gaps shown to the user), no leftover template names or emails, page count right, links correct.
- Deliver the files to the user (send file tool where available), named `<Company> - <Role> - <YYYY-MM-DD>`.
- Give the full text of the CV and letter in the reply as well, so the user can paste it into an application form.

## Tracker without Reactive Resume

Keep the user's private `private/applications-tracker.csv` (create it from `templates/applications-tracker.csv` if missing; never write to the templates) with columns: date, company, role, link, status, follow_up_date, next_action, contact, notes. Append a row per application and give the user the updated file. Status is `saved` until the **user** says they have applied.
