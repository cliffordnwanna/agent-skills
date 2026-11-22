# Typed, validated output

The kit defines its contracts as Pydantic v2 models in `schemas/models.py`: `Posting`, `Flag`, `Match`, `CV` (with `Bullet`), `Answer`, `ApplicationPackage`, `JobLead` and `DiscoveryResult`. The rules of this skill are encoded in the validators, so a violated rule fails loudly instead of slipping through.

## What the models enforce
- **Truth rule (a heuristic, not a guarantee):** every CV bullet names its `evidence`; a bullet containing a digit or a common number word ("percent", "half", "doubled", "thirty" and similar) is rejected unless `figure_confirmed` is true. The check cannot catch every quantity (for example "one third"), and `figure_confirmed` is set by whoever builds the JSON. You still have to follow the truth rule yourself.
- **No claim without evidence:** a match marked strong or transferable must cite evidence.
- **Flag, don't block:** flags are data. No flag level prevents a package from validating, except that a **high-risk** legitimacy finding forbids `outreach`.
- **Every posting question is answered:** unanswered questions fail validation.
- **Lean limits:** at most three improve-next items, five next steps, a cover letter of at most 250 words.
- **Discovery:** at most five leads; `date_verified` requires a `posted_date`.

## How to use it in a run
1. After analysing a job, assemble the data as an `ApplicationPackage` (or a `DiscoveryResult`) in JSON.
2. **If a code tool is available**, install the requirements (`pip install -r requirements.txt`), save the JSON, and run `python scripts/validate_output.py package <file>`. Fix every reported error and re-run. Then render documents with `python scripts/render_docs.py <file> <outdir>` (separate, dated DOCX files; add `--pdf` to also convert with LibreOffice when it is installed, otherwise the script prints a notice and the DOCX files still arrive). Otherwise build the files with the client's own document tools from the validated content.
3. **If no code tool is available**, check the data by hand against the rules above before generating documents.
4. Do not show the JSON to the user unless they ask. The user sees the lean output.

## Where hard guarantees come from
In a chat, enforcement happens only when the validation script is run. Nothing forces the model to produce valid JSON the first time. For a hard guarantee, export the JSON Schema (`python scripts/export_schemas.py`, files in `schemas/`) and pass it as the response format of a model API that supports structured outputs, then validate again with the Pydantic models.
