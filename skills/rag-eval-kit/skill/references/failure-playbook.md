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
| `ragkit run` says "Waiting for a person" (`waiting_for_human` with `--json`) | There is no frozen question set yet. This is not an error. | Tell the user what a person must do (import or generate, review, freeze). Run again afterwards. | Do the review or freeze for them. |
| `ragkit run` blocked: "working tree is dirty" | The app's repository has uncommitted changes, so the tested version is not exact. | Ask the user to commit or stash their own changes. | Discard or commit changes you did not make. |
| `ragkit run` blocked: output folder inside the target repository | The tool's own files would make the repository dirty. | Add the folder to that repository's `.gitignore` and commit it, or move `output` outside. | Turn off the clean-tree check. |
| `ragkit run` blocked: predictions are for a different revision | The app changed since those predictions were made. | Use a new `output` folder for the new revision. | Reuse or edit the old predictions. |
| `ragkit run` blocked: dataset or corpus changed since the freeze | A frozen file was edited. | Restore the original files. If the change was wanted, make a new reviewed and frozen dataset. | Edit the fingerprints to match. |
| `ragkit run` blocked: the target failed on some questions | Timeouts, errors or a wrong address. Failed questions are never dropped silently. | Look at the failures file next to the predictions (each has a kind: timeout, connection or error). Fix the cause. Only if the user agrees, run again with `--allow-failures` to score the rest and count the failures in the error rate. | Use `--allow-failures` to hide a broken app. |
| A ceiling shows `UNASSESSABLE` | The measurement is missing: no failures file, no token counts, or no pricing file. | Say what is missing. For cost, the app must report input and output tokens and the user must supply prices. | Treat it as passing. |
| `compare` refuses: runs are incompatible (`hit_level`) | One run counts repeated chunks of a document and the other does not. | Run both with the same `--hit-level` (document is the default). | Use `--allow-incompatible` without saying how it weakens the result. |
| `ragkit adapter test` fails at "read_response" | A response path in `adapter.json` does not match the app's JSON. | Use the key names it lists to fix `answer_path`, `contexts_path`, `source_ids_path` or `retrieval_mode_path`. Paths can use list positions, such as `choices.0.message.content`. | Guess paths without testing again. |
| `ragkit adapter test` fails at "request" | The app is not running, the address or login header is wrong, or the body shape is wrong. | Check the address and headers. If the app needs another body shape, add a `request` template. | Retry in a loop. |
| Sources come back as a list of objects | Paths only read lists of text, and wildcard paths are not built yet. | Use a JSONL file or a thin wrapper endpoint that returns lists of text. | Pretend the objects are text. |

## When unsure

Stop, say what you know and what you do not, and ask the user. A clear "I could not verify this" is the right output.
