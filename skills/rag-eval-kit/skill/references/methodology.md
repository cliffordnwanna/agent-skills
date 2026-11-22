# Methodology (summary)

## What is measured

**Offline, lexical track** (free, deterministic): Hit@1, Hit@3, Recall@3, MRR and abstention accuracy, computed from the source IDs the target returned compared with the reviewed `expected_source_ids`. Results are labelled lexical, measure source matching only (not semantic relevance or answer quality), and are never combined with semantic results.

**Semantic track** (paid): DeepEval faithfulness, answer relevancy, contextual recall, contextual precision and contextual relevancy, scored by a configurable judge model. Only records whose `retrieval_mode` is `semantic` are accepted. Each judge metric runs `--repeats` times (default 3, range 1 to 5) and the spread is reported. If a record has no retrieved context, the metrics that need it are marked unassessable, not scored as zero.

## Dataset

Questions come from a licensed corpus with a recorded commit, licence and file hashes. A person reviews every question before the freeze. The freeze records the corpus hash, golden hash, dev and held-out hashes, the split seed and the approver. The split is stratified by category, and questions that share an evidence span stay together so near-duplicates cannot sit in both splits. Frozen directories are never overwritten.

## Comparing runs

Runs are compared only if target-independent inputs match: dataset hash, corpus hash, judge and retrieval mode. Per-question score differences get a paired bootstrap 95% interval. Pass/fail changes at a threshold get an exact two-sided McNemar test. A single pass rate gets a Wilson interval. A verdict must follow thresholds agreed in advance.

## Limits (state these in every report)

- About 20 held-out questions gives wide intervals. Treat results as exploratory.
- LLM judges are noisy and can share biases with the system that generated the answer. Prefer a judge model different from the system under test, and read the per-question failures, not only averages.
- Reference answers and evidence are written by a person; a mistaken reference biases every score.
- The cost guard is local accounting, not a provider billing cap.
- Context and source-ID metrics need the application to return what it retrieved.
- Judge compatibility is checked per model. The only judge verified so far is `gpt-4.1-mini`, on three fixture examples.
- Text RAG only.
