# Pre-screen of 60 candidate questions

Status: **recommendations only, not approval.** `review.csv` is unchanged and its `keep` column is still blank. `review_prescreen.csv` adds `prescreen` (ACCEPT / EDIT / DROP) and `prescreen_notes`. Final decisions belong to the owner.

Checks run: evidence spans exist in the corpus; every multi-document case has evidence in each listed source; question near-duplicates; paraphrase wording overlap; unanswerable terms searched in the corpus. All 60 were also read by hand.

| Category | Accept | Edit | Drop | Left if edits kept | Target |
|---|---|---|---|---|---|
| direct | 12 | 0 | 0 | 12 | 10 |
| paraphrased | 11 | 0 | 1 | 11 | 10 |
| multi_document | 6 | 2 | 4 | 8 | 10 |
| difficult_retrieval | 8 | 0 | 4 | 8 | 10 |
| unanswerable | 10 | 2 | 0 | 12 | 10 |

## Gaps
- Two more genuine multi-document questions and two more difficult-retrieval questions are needed to reach 10 each.
- Most unanswerable questions are plainly out of domain (pricing, hosting). Add near-miss questions about topics the corpus touches but does not answer.
- Several cases share a source fact (e.g. direct-03 / paraphrased-01). Keep them in the same split when freezing so the held-out set does not leak.
- Reference answers for multi-document cases are syntheses; the evidence spans support them but no one has verified the wording.
- Candidates were authored offline without a model. Their quality is unreviewed.
