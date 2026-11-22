# Failure playbook

For each symptom: what it usually means, what to do, and what not to do.

| Symptom | Usually means | Do | Do not |
|---|---|---|---|
| `corpus inspect` says `Corpus content hash mismatch` | Corpus bytes changed. Most often line endings were converted by a git or editor setting. | Restore the files byte-for-byte from the source (for example copy from the original repository, not through a tool that rewrites line endings). Check the `.gitattributes` for the benchmark folder is present. Re-run `corpus inspect`. | Edit `provenance.json` hashes to match, or edit corpus files. |
| `dataset review` reports rows with no decision | `keep` column has blanks. | Ask the user to decide every row. | Fill `keep` for them. |
| `dataset freeze` refuses | Output directory exists, or the sheet is invalid, or `--approved-by` is missing. | Use a new directory name; fix the sheet; ask the user for the approver name. | Delete a frozen directory, or invent an approver. |
| `predict` exits non-zero and lists failed questions | The target errored, timed out or did not return the expected fields. | Read the listed failures. Fix the adapter config (field paths, endpoint, auth env var) or the target. Retries are bounded (0 to 3). Re-run into a **new** output file. | Drop failed questions from the file, or evaluate a partial set as if it were complete. |
| Faithfulness or context metrics are "unassessable" | The target did not return retrieved contexts. | Report them as unassessable. Offer to expose contexts from the target. | Report them as zero, or hand-write contexts. |
| `evaluate` is blocked: budget | Budget is zero (default) or the reservation would exceed the cap, or usage was unknown. | Run `ragkit plan` and show the estimate. Ask the user whether to set or raise the cap. | Raise the cap or edit the budget variable yourself. |
| Live judge errors or odd scores | The judge model may not be compatible with the metric prompts. Only `gpt-4.1-mini` on three fixture examples has been verified. | Report the model and the failure. Try the offline track meanwhile. | Switch models silently or claim the new model is verified. |
| `compare` refuses | Dataset hash, corpus hash, judge or retrieval mode differ between runs. | Re-run the "after" with the same inputs. Explain what differed. | Use `--allow-incompatible` without telling the user how it weakens the result. |
| Builder adapter refuses semantic mode | The Builder is not reporting `live` mode. | Start the Builder in live mode, or use the offline lexical track. | Pretend a lexical run is semantic. |
| Results look too good | Leakage, a reused held-out split, a judge that shares the generator's biases, or an easy dataset. | Check held-out has not been used before; check the judge differs from the generator; read the failures. | Publish the number. |
| Held-out split already used and results disappointed | Temptation to tweak and re-run. | State plainly that a second held-out run is no longer a clean test. Fix against dev and, if needed, create a new reviewed dataset. | Re-run held-out repeatedly until it passes. |
| Tests or CI differ on Windows vs Linux | Line endings or path handling. | Compare file bytes first, then paths. | Normalise benchmark files. |

## When unsure

Stop, say what you know and what you do not, and ask the user. A clear "I could not verify this" is the right output.
