# Golden-set review rubric (for the human reviewer)

Everything downstream (baseline, fix, held-out report) rests on these questions being right. **The user reviews and decides. You may explain this rubric, point at rows that look suspicious, and validate the sheet with `ragkit dataset review`. You must not fill the `keep` column or call any question reviewed.**

Questions that come from `ragkit dataset import` get exactly the same treatment: the import checks each one against the documents, but a person still has to read it and decide. Do not treat "it imported without errors" as "it is a good question".

Pre-screen files (for example `review_prescreen.csv` and `PRESCREEN.md` in the benchmark) are recommendations from an automated pass. They are not approval. Ask the user to read the DROP rows and any replacements properly, and to check the evidence on the ACCEPT rows too.

## Per question, the reviewer checks

1. **Evidence exists.** Each `reference_evidence` span is present in the corpus, word for word. Open the source file; do not trust the sheet.
2. **Sources are right.** `expected_source_ids` lists every document the answer needs, and no extra ones. A multi-document question needs supporting evidence in each listed source.
3. **The answer is supported by the evidence alone.** If the reference answer needs outside knowledge, edit it or drop the row. Multi-document answers are syntheses; check the wording is actually supported.
4. **The question is natural and unambiguous.** A user could plausibly ask it. It has one defensible answer.
5. **Paraphrases are real paraphrases.** A paraphrased question must not reuse the original's key wording, or it tests keyword matching, not retrieval.
6. **Unanswerable really is unanswerable.** Search the corpus for the key terms. Prefer near-miss questions about topics the corpus touches but does not answer; plainly out-of-domain questions (pricing, hosting) are easy and teach little.
7. **No near-duplicates.** Two questions testing the same fact add little and can leak between splits. The freeze keeps questions that share evidence in the same split, but fewer duplicates is better.
8. **Category fit.** direct, paraphrased, multi_document, difficult_retrieval or unanswerable, matching what the question actually tests.

## Balance

The benchmark aims for a similar count in each category. After decisions, check the counts per category. If a category is short (for example multi-document or difficult retrieval), the reviewer should write replacements by hand, from the corpus, rather than keep weak rows to fill the number.

## Recording decisions

For every row the reviewer sets `keep` to `yes` or `no`, and edits text where needed. Blank rows block freezing. When the reviewer says the sheet is approved and gives their name, run `ragkit dataset review` and then `ragkit dataset freeze ... --approved-by "<their name>"`. The name is theirs to supply.

## Be honest about review quality

Record roughly how long the review took and what was and was not checked (for example "evidence verified for all kept rows; wording of multi-document answers not independently verified"). Put that in the final report.
