# Stage 1 reuse study

Read-only source review, 2026-11-18. Scope: the existing text-only workflow; **retain DeepEval as the metric engine**. No inspected evidence justifies replacing it. Recommendations below are design decisions, not implemented features or benchmark results.

## Inspected revisions and licenses

GitHub commit responses resolved these revisions; actual `LICENSE` contents were inspected, not just badges. `Giskard-AI/giskard` redirects to `giskard-oss`.

| Repository | Inspected commit | Actual license |
| --- | --- | --- |
| unshDee/proofrag | `ea688e309a73d155756bf1a33e2d07bf13bb5cfb` | [MIT][p-license] |
| vectara/open-rag-eval | `e05341bc19bbc2944a1e28634a6f98b32e7a3238` | [Apache-2.0][o-license] |
| Giskard-AI/giskard, current | `bfda958b3eee42927f961b26e33254ece3d46884` | [Apache-2.0][g-license] |
| Giskard-AI/giskard, historical `v2.18.0` | `b956fc2e60ff0f6edac7c013ba32f5352e843e07` | [Apache-2.0][g2-license] |

MIT requires retaining copyright/permission notices for distributed copies or substantial portions. Apache-2.0 requires the license, applicable notices, and modification notices when relevant; it includes patent conditions and no general trademark grant. Models, corpora and transitive dependencies need separate checks. Giskard's current generated [third-party report][g-notices] labels its project MIT, conflicting with root `LICENSE`; do not treat that report as licensing clearance. No third-party implementation, prompts or datasets are copied here.

## Findings and reuse boundary

### ProofRAG: portable artifacts and comparison discipline

- **Contract:** goldenset JSONL contains `id`, `question`, `gold_answer`, `gold_contexts`, difficulty, sources and context metadata. Prediction JSONL normalizes to `id`, `answer`, `retrieved_contexts`; string-only adapters produce empty contexts. [Source][p-contract]; [normalization][p-run]. Inspected [tests][p-tests] require unique, exact prediction-ID coverage: missing, duplicate and unexpected IDs fail.
- **Cross-judge refusal:** the [CLI][p-cli] rejects incompatible configurations and judge fingerprints (exit 2); judge mismatch alone has an explicit warning-producing override. The underlying [diff function][p-diff] merely reports mismatches. Configuration fields include backend, cutoff, count, dataset fingerprint, matcher and generation-metric schema. Do not equate identically named metrics across engines.
- **Review/freeze:** [validation][p-workflow] checks structure, not truth; the workflow recommends reviewing then committing plain files. The RFC case study already has [content-bound review decisions][p-review], reviewer/date and approval checks. This is meaningful prior art, but case-study machinery is not a general application approval/freeze service.
- **Reuse:** ideas for strict file boundaries, provenance and comparison gates. Build our own small adapter and review state machine; do not add a second orchestration dependency. ProofRAG itself [supports DeepEval][p-judges], reinforcing retention rather than migration.

### Open RAG Eval: reference-free diagnostics, not independent ground truth

- **Contract:** [CSV loader][o-loader] expects `query`, `passage_id`, `passage`, `generated_answer`; `query_id` and `query_run` group passage rows. Missing IDs become per-row UUIDs, so always supply stable IDs. Expected answers can join from a separate queries dataframe. Numeric answer citations map to passages. No-answer/API-error runs are skipped: our adapter must instead retain explicit failure/abstention records.
- **Reference-free scope:** [UMBRELA][o-metrics] judges retrieved-passage relevance; [AutoNuggetizer][o-nuggets] generates answer-coverage targets from those retrieved passages, filtered by relevance. No manually authored answer is required, but context and model judgments still are. Consequently, omitted evidence cannot supply nuggets: high coverage is not proof of corpus-wide completeness, recall or factual correctness. Changing retrieved evidence also changes the coverage target.
- [Comparison plotting][o-plot] and its [TREC implementation][o-trec] were inspected; no equivalent judge-fingerprint refusal was found there. File output/plots are not approval or freeze enforcement.
- **Reuse:** ideas for optional reference-free diagnostic labels and separate retrieval/generation reporting. Defer this dependency; it adds another metric/model stack. Default judges and factuality backends can require credentials, downloads or commercial services ([README][o-readme]); reference-free does not mean offline or free.

### Giskard: versioned question taxonomy, not a drop-in workflow

- Historical RAGET [documents][g2-taxonomy] simple, complex/paraphrased, distracting, situational, double and conversational questions. The [actual exports][g2-exports] additionally include out-of-scope generation. Its [attribution map][g2-map] mentions multi-context, but that is not an exported generator in this revision; category labels are not evidence of an implementation or causal fault diagnosis.
- Historical [QATestset][g2-testset] supports editable dataframe/JSONL round trips with references, history and metadata; this is persistence, not an approval/freeze guarantee.
- Current Giskard is a [v3 rewrite][g-readme], not that API. Its [quality registry][g-quality] contains direct hallucination, sycophancy, split-question, multi-topic and out-of-scope generators. Missing knowledge bases warn and skip knowledge-base scenarios. [Split questions][g-split] and [multi-topic][g-multi] skip single-turn mode. Text-only must not silently imply support for conversational evaluation.
- **Reuse:** taxonomy and coverage ideas, with explicit version attribution. Build text-case generation/review around the existing engine; defer Giskard integration rather than importing its evolving scan stack.

## What this application should own

Keep DeepEval through its existing dependency. Build a versioned text-case/prediction contract; immutable approved snapshots binding corpus, dataset and review decisions; reviewer/time/reason audit records; exact ID joins; explicit skipped/error/abstention outcomes; and run manifests recording engine/package version, judge/model/provider, rubric, configuration and evidence hashes. Refuse comparable-regression claims across mismatched manifests. Treat reference-free diagnostics separately from reference-backed correctness and retrieval recall. Require semantic human review before freezing generated cases.

## Verification and limitations

The three repositories were shallow-cloned outside both project repositories on 2026-11-18. HEADs and root license files were verified in each clone; revisions match the pinned revisions in this report. Source and test findings were inspected at those pinned revisions. No upstream code was run, installed or imported, and no paid/model services were called. The exact temporary clone folder was removed after inspection. These are source-review findings, not execution verification. Application tests, code and other documentation remain outside this study's ownership.

[p-license]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/LICENSE
[o-license]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/LICENSE
[g-license]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/LICENSE
[g2-license]: https://github.com/Giskard-AI/giskard-oss/blob/b956fc2e60ff0f6edac7c013ba32f5352e843e07/LICENSE
[g-notices]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/THIRD_PARTY_NOTICES.md
[p-contract]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/src/proofrag/goldenset.py
[p-run]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/src/proofrag/run.py#L199-L250
[p-tests]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/tests/test_integrity.py#L131-L139
[p-cli]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/src/proofrag/cli.py#L308-L323
[p-diff]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/src/proofrag/diffing.py
[p-workflow]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/docs/workflow.md
[p-review]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/case_studies/http_rfc_metadata/audit_goldenset.py
[p-judges]: https://github.com/unshDee/proofrag/blob/ea688e309a73d155756bf1a33e2d07bf13bb5cfb/docs/judges.md
[o-loader]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/open_rag_eval/rag_results_loader.py
[o-metrics]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/METRICS.md
[o-nuggets]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/open_rag_eval/metrics/autonugget_metric.py#L181-L209
[o-plot]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/open_rag_eval/plot_results.py
[o-trec]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/open_rag_eval/evaluators/trec_evaluator.py
[o-readme]: https://github.com/vectara/open-rag-eval/blob/e05341bc19bbc2944a1e28634a6f98b32e7a3238/README.md
[g2-taxonomy]: https://github.com/Giskard-AI/giskard-oss/blob/b956fc2e60ff0f6edac7c013ba32f5352e843e07/docs/open_source/testset_generation/testset_generation/index.md
[g2-exports]: https://github.com/Giskard-AI/giskard-oss/blob/b956fc2e60ff0f6edac7c013ba32f5352e843e07/giskard/rag/question_generators/__init__.py
[g2-map]: https://github.com/Giskard-AI/giskard-oss/blob/b956fc2e60ff0f6edac7c013ba32f5352e843e07/giskard/rag/question_generators/question_types.py
[g2-testset]: https://github.com/Giskard-AI/giskard-oss/blob/b956fc2e60ff0f6edac7c013ba32f5352e843e07/giskard/rag/testset.py#L24-L115
[g-readme]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/README.md
[g-quality]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/libs/giskard-scan/src/giskard/scan/quality.py
[g-split]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/libs/giskard-scan/src/giskard/scan/generators/knowledge_base/split_questions.py
[g-multi]: https://github.com/Giskard-AI/giskard-oss/blob/bfda958b3eee42927f961b26e33254ece3d46884/libs/giskard-scan/src/giskard/scan/generators/knowledge_base/multi_topic.py
