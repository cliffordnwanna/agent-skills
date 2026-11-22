# Methodology

## What is measured

**Offline, lexical track** (free, deterministic): Hit@1, Hit@3, Recall@3, MRR and abstention accuracy, computed from the source IDs the target returned versus the reviewed `expected_source_ids`. Results are labelled lexical and are never combined with semantic results.

**Semantic track** (paid): DeepEval faithfulness, answer relevancy, contextual recall, contextual precision and contextual relevancy, scored by a configurable judge model. Only records whose `retrieval_mode` is `semantic` are accepted. Each judge metric is run `--repeats` times (default 3) and the spread is reported. If a record has no retrieved context, the metrics that need it are marked unassessable, not zero.

## Dataset

Questions come from a licensed corpus with a recorded commit, licence and file hashes. Categories: direct, paraphrased, multi-document, difficult retrieval, unanswerable. A person reviews every question before freezing; blank decisions block freezing. The freeze records the corpus hash, golden hash, dev and held-out hashes, the split seed and the approver.

The split is stratified by category. Questions that share an evidence span are kept together so a near-duplicate cannot sit in both splits. Diagnose and fix using the dev split; use the held-out split once, after the change and configuration are frozen.

## Comparing runs

Runs are compared only if target-independent inputs match: dataset hash, corpus hash, judge and retrieval mode. Per-question score differences get a paired bootstrap 95% interval. Pass/fail flips at a threshold get an exact two-sided McNemar test. A single pass rate gets a Wilson interval. A verdict must follow the thresholds agreed in advance, not whichever metric improved.

## Honest limits

- About 20 held-out questions gives wide intervals. Treat results as exploratory.
- LLM judges are noisy and can share biases with the generator. Prefer a judge model different from the system under test, and read the per-question failures, not only averages.
- Reference answers and evidence were authored by a person from the corpus; a biased or mistaken reference biases every score.
