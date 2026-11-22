# Report template

Fill every field from a run file, `compare` output, or something the user told you in this conversation. If a field has no source, write "not available". **Do not write a number that is not in a run file.** If there is no frozen dataset and no completed before/after run, the report is a status report and must say there is no result.

```
# RAG evaluation report: <system name>

Status: <draft | final>      Date: <YYYY-MM-DD>
Skill version: v0.1 (workflow verified offline; no live case study unless stated here)

## Question
Did <change> make <system> better, judged by <primary metric> on <dataset>?

## Setup
- System under test: <name>, before revision <sha>, after revision <sha>
- Adapter: <generic | builder>, retrieval mode: <lexical | semantic>
- Corpus: <name, source revision, licence>, corpus hash <hash>
- Dataset: freeze approved by <name> on <date>; dataset hash <hash>; dev <n> / held-out <n>; split seed <seed>
- Judge (semantic only): <model>, repeats <n>, price source and check date <...>

## Pre-agreed rule (written before the held-out run)
<paste thresholds.md: primary metric, pass rule, improvement rule, guard metrics, budget>

## Review quality
<how long the golden-set review took; what was and was not checked>

## Results (copy from compare output; do not round differently)
| Metric | Before | After | Difference | 95% interval | Pass/fail flips (McNemar) |
|---|---|---|---|---|---|
| <primary metric> | | | | | |

Unassessable or failed items: <list, with reasons>
Cost: <USD spent against cap, local accounting>; target application costs not included

## Verdict (apply the pre-agreed rule only)
<improved | no evidence of a change | regressed | invalid> because <rule text and the numbers above>

## Failures worth reading
<the specific questions that failed, with what the system answered and why>

## Limits
- About <n> held-out questions: wide intervals, exploratory result
- Judge noise and shared bias; reference answers written by a person
- Cost guard is local accounting, not a billing cap
- Text RAG only
- <anything else specific to this run>

## What was not done
<for example: no second judge model, no repeat of held-out, no human re-review of references>
```
