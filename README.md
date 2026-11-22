# agent-skills

Reusable agent skills for Claude and other AI agents.

| Skill | What it is | Status |
|---|---|---|
| [`job-application-kit`](skills/job-application-kit/) | Turns pasted job postings into tailored application files (CV, cover letter, answers) with a truth rule and typed validation. Never submits anything. | Validator, renderer and tests run and pass. The workflow has not yet been tested on real job postings. |
| [`rag-eval-kit`](skills/rag-eval-kit/) | Local tooling for evaluating RAG systems. | Early stage: offline checks and a bounded DeepEval compatibility spike. Not yet a complete evaluator. |

Each skill has its own README with install steps and an honest status section.

**No personal data lives here.** The skills are generic: rules, templates and fictional examples only. Anything personal (preferences, pay figures, achievements) belongs in a private folder in your own workspace, never in this repository.

Licensed under Apache-2.0 (see [LICENSE](LICENSE)).
