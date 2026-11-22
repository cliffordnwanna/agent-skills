"""How ragkit talks to people: a readable summary by default, JSON with --json.

Every command that prints a result goes through ``emit``. By default it prints a short summary
with checkmarks and a "Next:" line. With ``--json`` (or RAGKIT_OUTPUT=json) it prints exactly
the JSON that scripts and agents rely on. Exit codes are never affected by the output mode.
"""

import json
import os
import sys
import textwrap
from typing import Any

import typer

WIDTH = 92


def json_mode() -> bool:
    return os.environ.get("RAGKIT_OUTPUT", "").strip().lower() == "json"


def _unicode_ok() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✓✗·".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _marks() -> dict[str, str]:
    if _unicode_ok():
        return {"ok": "✓", "bad": "✗", "skip": "·", "wait": "…", "todo": "○", "warn": "!"}
    return {"ok": "[ok]", "bad": "[x]", "skip": "-", "wait": "...", "todo": "( )", "warn": "[!]"}


def _style(text: str, colour: str | None = None, bold: bool = False) -> str:
    if os.environ.get("NO_COLOR") or colour is None and not bold:
        return text
    return typer.style(text, fg=colour, bold=bold)


def _mark(kind: str) -> str:
    colours = {"ok": "green", "bad": "red", "warn": "yellow", "wait": "yellow"}
    return _style(_marks()[kind], colours.get(kind), bold=kind in {"ok", "bad"})


def _wrap(text: str, indent: str = "  ") -> list[str]:
    return textwrap.wrap(str(text), WIDTH, initial_indent=indent, subsequent_indent=indent) or [""]


def _score(value: Any) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _ms(value: Any) -> str:
    return "n/a" if value is None else f"{value:,.0f} ms"


def _pct(value: Any) -> str:
    return "unknown" if value is None else f"{value * 100:.1f}%"


def _short(path: Any) -> str:
    return os.path.basename(str(path)) if path else ""


def _next(*lines: str) -> list[str]:
    if not lines:
        return []
    if len(lines) == 1:
        return ["", f"{_style('Next:', bold=True)} {lines[0]}"]
    return ["", _style("Next:", bold=True), *[f"  - {line}" for line in lines]]


def _wrap_item(text: str) -> list[str]:
    """Wrap a numbered step so continuation lines line up under the text."""
    head = text.split(" ", 1)[0]
    hanging = "     " if head.rstrip(".").isdigit() else "  "
    return textwrap.wrap(text, WIDTH, initial_indent="  ", subsequent_indent=hanging)


def _plain_paths(command: str) -> str:
    """Show paths relative to the current folder so commands are shorter to read."""
    return command.replace(os.getcwd() + os.sep, "")


# ------------------------------------------------------------------ renderers
def _scores(label: str, metrics: dict[str, Any]) -> list[str]:
    shown, missing = [], []
    for name, result in metrics.items():
        score = result.get("score") if isinstance(result, dict) else None
        short = name.replace("_at_", "@")
        if score is None:
            missing.append(short)
        else:
            shown.append(f"{short} {score:.2f}")
    lines = _wrap(f"{label}: " + ("  ".join(shown) or "none could be scored"))
    if missing:
        lines += _wrap(f"Not assessable here: {', '.join(missing)}")
    return lines


def _smoke_passed(v: dict, **_: Any) -> list[str]:
    run = v.get("result", {})
    n = run.get("counts", {}).get("questions", 0)
    return [
        f"{_mark('ok')} {_style('Smoke test passed', bold=True)}",
        *_wrap(f"A tiny fake RAG app on this computer answered {n} questions and was scored."),
        *_scores("Free retrieval scores", run.get("metrics", {})),
        "  Paid calls: 0. No key was needed.",
        *_next("run `ragkit init` in your own project."),
    ]


def _smoke_failed(v: dict, **_: Any) -> list[str]:
    lines = [f"{_mark('bad')} {_style('Smoke test failed', bold=True)}"]
    lines += [f"  {f.get('question_id')}: {f.get('error')}" for f in v.get("failed", [])]
    return lines + _next("run again with --json for details, and check the install.")


def _doctor(v: dict, **_: Any) -> list[str]:
    ver = v.get("versions", {})
    lines = [
        f"{_mark('ok')} {_style('Everything needed is installed', bold=True)}",
        f"  Python {ver.get('python', '?')}, ragkit {ver.get('rag-eval-kit', '?')}, "
        f"deepeval {ver.get('deepeval', '?')}",
        f"  Judge key set: {'yes' if v.get('judge_key_configured') else 'no (only needed for paid steps)'}",
        f"  Telemetry: {v.get('telemetry', '?')}. Network checked: no. Paid calls: {v.get('paid_calls', 0)}.",
    ]
    target = v.get("target")
    if target:
        lines.append(
            f"  {_mark('ok')} Target app checkout is exactly {str(target.get('commit', ''))[:7]} "
            f"({target.get('working_tree', '?')})"
        )
    return lines + _next("`ragkit smoke` to see a free end-to-end run.")


def _corpus_inspect(v: dict, **_: Any) -> list[str]:
    docs = v.get("documents", [])
    ok_limits = v.get("builder_limits_ok")
    return [
        f"{_mark('ok')} {_style('Documents verified', bold=True)}: {v.get('name', '')}",
        f"  {len(docs)} documents, {v.get('total_characters', 0):,} characters; fingerprints match.",
        f"  {_mark('ok' if ok_limits else 'bad')} Within the size limits (20 documents, 100,000 characters)"
        if ok_limits is not None
        else "",
        f"  Source: {v.get('source_repository', '')} @ {str(v.get('source_revision', ''))[:7]}, "
        f"licence {v.get('license', '?')}",
    ]


def _provenance_written(v: dict, **_: Any) -> list[str]:
    return [
        f"{_mark('ok')} {_style('Wrote provenance.json', bold=True)} for {v.get('count', 0)} documents: "
        + ", ".join(v.get("documents", [])),
        *_next("write your questions, then `ragkit dataset import <file> --corpus-dir <folder> "
               "--output-dir <new folder>`."),
    ]  # fmt: skip


def _imported(v: dict, **_: Any) -> list[str]:
    return [
        f"{_mark('ok')} {_style('Imported ' + str(v.get('question_count', '?')) + ' questions', bold=True)}",
        f"  {_mark('warn')} They are NOT approved. A person must read every question.",
        *_next("open review.csv, write yes or no in the `keep` column of every row, then "
               "`ragkit dataset review` and `ragkit dataset freeze --approved-by \"<name>\"`."),
    ]  # fmt: skip


def _candidates(v: dict, **_: Any) -> list[str]:
    return _imported(v)


def _review_valid(v: dict, **_: Any) -> list[str]:
    cats = ", ".join(f"{k} {n}" for k, n in v.get("by_category", {}).items())
    return [
        f"{_mark('ok')} {_style('Review sheet is valid', bold=True)}: kept {v.get('kept', 0)}, "
        f"dropped {v.get('dropped', 0)} of {v.get('rows', 0)}",
        *_wrap(f"Kept by category: {cats}"),
        *_next('`ragkit dataset freeze ... --approved-by "<your name>"` once you are happy.'),
    ]


def _frozen(v: dict, **_: Any) -> list[str]:
    counts = v.get("counts", {})
    return [
        f"{_mark('ok')} {_style('Question set frozen', bold=True)} ({v.get('review_status', '')})",
        f"  {counts.get('golden', 0)} questions: {counts.get('dev', 0)} dev (for fixing) and "
        f"{counts.get('heldout', 0)} held-out (use once, at the end).",
        "  Fingerprints are recorded in freeze.json. The folder cannot be overwritten.",
        *_next("point `dataset:` in ragkit.yaml at this folder, then `ragkit run`."),
    ]


def _initialised(v: dict, **_: Any) -> list[str]:
    skill = v.get("skill", {})
    lines = [
        f"{_mark('ok')} {_style('Created', bold=True)} " + " and ".join(v.get("written", [])),
        f"  {_mark('ok') if skill.get('copied') else _mark('skip')} "
        + (
            f"Agent skill copied to {skill.get('path')}"
            if skill.get("copied")
            else "Agent skill not copied"
        ),
    ]
    steps = v.get("next_steps", [])
    return (
        lines + ["", _style("Next:", bold=True)] + [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    )


def _init_partial(v: dict, **_: Any) -> list[str]:
    return [
        f"{_mark('warn')} {_style('Files written, but the skill was not copied', bold=True)}",
        *_wrap(v.get("skill_error", "")),
    ]


def _adapter_ok(v: dict, **_: Any) -> list[str]:
    ex = v.get("extracted", {})
    answer = str(ex.get("answer", "")).replace("\n", " ")
    return [
        f"{_mark('ok')} {_style('Your app answered', bold=True)} in {_ms(v.get('latency_ms'))}",
        *_wrap(f"Answer: {answer[:160]}{'...' if len(answer) > 160 else ''}"),
        f"  Passages found: {ex.get('retrieved_context_count', 0)}; sources: "
        f"{', '.join(ex.get('retrieved_source_ids', [])) or 'none'}; mode: {ex.get('retrieval_mode')}",
        f"  Sent to {v.get('url')}. Nothing was saved.",
        *_next("`ragkit run` once your documents and frozen questions are ready."),
    ]


def _adapter_failed(v: dict, **_: Any) -> list[str]:
    stage = "reach your app" if v.get("stage") == "request" else "read your app's answer"
    lines = [
        f"{_mark('bad')} {_style('Could not ' + stage, bold=True)}",
        *_wrap(v.get("reason", "")),
    ]
    if v.get("response_top_level_keys") is not None:
        lines.append(
            f"  Your app's response has these top-level keys: {v['response_top_level_keys']}"
        )
    return lines + _next(
        v.get("hint") or "check the address and headers in adapter.json, then try again."
    )


def _predict(v: dict, **_: Any) -> list[str]:
    failed = v.get("failed", [])
    done = v.get("predictions", 0)
    lines = [
        f"{_mark('ok' if not failed else 'bad')} "
        + _style(
            f"Asked your app {done + len(failed)} questions: {done} answered, {len(failed)} failed",
            bold=True,
        )
    ]
    for f in failed[:5]:
        lines.append(
            f"  {_mark('bad')} {f.get('question_id')}: {f.get('kind', 'error')}: {f.get('error', '')[:90]}"
        )
    if v.get("output"):
        lines.append(f"  Predictions: {v['output']}")
    if v.get("failures_file"):
        lines.append(f"  Failures file: {v['failures_file']}")
    if failed:
        return lines + _next(
            "fix the cause and run again, or add --allow-failures to score the rest."
        )
    return lines + _next("`ragkit evaluate <predictions> ...`, or let `ragkit run` do it.")


def _evaluation(v: dict, *, wrote: str | None = None, **_: Any) -> list[str]:
    c = v.get("counts", {})
    mode = v.get("retrieval_mode", "?")
    lines = [
        f"{_mark('ok')} {_style('Evaluation complete', bold=True)} ({mode}, "
        f"{'free' if mode == 'lexical' else 'paid judge'})",
        f"  Questions: {c.get('questions', 0)}; records: {c.get('total_records', 0)}; "
        f"invalid: {c.get('invalid_records', 0)}",
    ]
    label = "Retrieval scores" if mode == "lexical" else "Judge scores"
    level = f" ({v['hit_level']}-level)" if v.get("hit_level") else ""
    lines += _scores(f"{label}{level}", v.get("metrics", {}))
    obs = v.get("observability")
    if obs:
        lat = obs["latency_ms"]
        if lat.get("status") == "VERIFIED":
            small = ", few answers" if lat.get("low_sample") else ""
            lines.append(
                f"  Speed (measured by ragkit): median {_ms(lat['p50'])}, slow end {_ms(lat['p95'])} (n={lat['n']}{small})"
            )
        else:
            lines.append("  Speed: not recorded")
        err = obs["error_rate"]
        lines.append(
            f"  Errors: {_pct(err['rate'])} of questions"
            + ("" if err["status"] == "VERIFIED" else " (no failures file given)")
            + f"; unusable answers: {_pct(obs['invalid_rate']['rate'])}"
        )
        cost = obs["cost"]
        if cost["status"] in {"ESTIMATED", "PARTIAL"}:
            lines.append(
                f"  Cost of your app: about ${float(cost['per_query_usd']):.6f} per question (estimate)"
            )
        else:
            lines.append(f"  Cost of your app: unavailable ({cost['reason']})")
    check = v.get("ceiling_check")
    if check:
        marks = {"met": "ok", "failed": "bad", "unassessable": "warn"}
        lines.append(f"  {_mark(marks.get(check['overall'], 'warn'))} Ceilings: {check['overall']}")
        for item in check["checks"]:
            observed = "not measured" if item["observed"] is None else f"{item['observed']:g}"
            lines.append(
                f"      {item['ceiling']}: {observed} (limit {item['limit']:g}) {item['result']}"
            )
    if v.get("budget"):
        lines.append(
            f"  Judge spend: ${v['budget'].get('committed_or_reserved_usd', '?')} of ${v['budget'].get('limit_usd', '?')} cap"
        )
    for w in (v.get("warnings") or [])[:2]:
        lines += _wrap(f"{_mark('warn')} {w}")
    if wrote:
        lines.append(f"  Saved: {wrote}")
    return lines + _next("`ragkit report " + (_short(wrote) or "<run file>") + "` for the full write-up, "
                         "or `ragkit compare <before> <after>`.")  # fmt: skip


def _comparison(v: dict, **_: Any) -> list[str]:
    lines = [
        f"{_mark('ok' if v.get('compatible') else 'warn')} {_style('Compared two runs', bold=True)} "
        f"({v.get('paired_questions', 0)} paired questions)"
    ]
    for name, r in v.get("metric_deltas", {}).items():
        d, ci = r.get("mean_delta"), r.get("bootstrap_95_ci")
        shown = (
            "not assessable"
            if d is None
            else f"{d:+.3f}" + ("" if ci is None else f"  (95% range {ci[0]:+.3f} to {ci[1]:+.3f})")
        )
        lines.append(f"  {name}: {shown}")
    if v.get("compatibility_overridden"):
        lines.append(
            f"  {_mark('warn')} Compatibility was overridden; read the limits in the report."
        )
    return lines + _next(
        "judge the result by the rules you agreed before looking, then `ragkit report`."
    )


def _plan(v: dict, **_: Any) -> list[str]:
    return [
        f"{_mark('ok')} {_style('Paid-call estimate (no calls made)', bold=True)}",
        f"  Model {v.get('model')}: about {v.get('planned_call_count')} calls; worst-case judge cost "
        f"${v.get('judge_reservation_ceiling_usd')}",
        f"  Prices from {v.get('price_provenance', {}).get('source_url', '?')} "
        f"(checked {v.get('price_provenance', {}).get('checked_on', '?')}).",
        "  Not included: your app's own costs and dataset synthesis.",
        *_next(
            "only if you agree, add `--live --approve-paid --budget-usd <cap>` to a semantic `ragkit evaluate`."
        ),
    ]


_STAGE_LABELS = {
    "config": "settings", "corpus": "documents", "dataset": "questions", "revision": "app version",
    "predict": "ask your app", "evaluate": "score answers", "report": "write report",
}  # fmt: skip


def _stage_line(s: dict) -> str:
    state = s.get("state", "")
    mark = {
        "done": "ok",
        "skipped_already_done": "skip",
        "would_run": "todo",
        "would_skip": "skip",
    }.get(state, "ok")
    label = _STAGE_LABELS.get(s.get("stage", ""), s.get("stage", ""))
    detail = ""
    if s.get("stage") == "corpus":
        detail = f"{s.get('documents', 0)} documents verified"
    elif s.get("stage") == "dataset":
        detail = f"{s.get('questions', 0)} questions, {s.get('approved', '')}"
    elif s.get("stage") == "revision":
        detail = str(s.get("target_revision", ""))[:7]
    elif s.get("file"):
        detail = _short(s["file"])
    note = {
        "skipped_already_done": " (already done, skipped)",
        "would_run": " (would run)",
        "would_skip": " (would skip)",
    }.get(state, "")
    return f"  {_mark(mark)} {label:<14} {detail}{note}".rstrip()


def _run(v: dict, **_: Any) -> list[str]:
    status, split = v.get("status"), v.get("split", "dev")
    stages = [_stage_line(s) for s in v.get("stages", [])]
    if status == "completed":
        head = f"{_mark('ok')} {_style('ragkit run finished', bold=True)} ({split} set, free scoring, 0 paid calls)"
        tail = []
        if v.get("scores"):
            tail += _scores(
                "Retrieval scores (free: did it find the right documents?)",
                {k: {"score": s} for k, s in v["scores"].items()},
            )
        if v.get("latency_p95_ms") is not None:
            tail.append(
                f"  Speed: median {_ms(v.get('latency_p50_ms'))}, slow end {_ms(v['latency_p95_ms'])}"
            )
        if v.get("error_rate") is not None:
            tail.append(f"  Errors: {_pct(v['error_rate'])} of questions")
        if v.get("ceilings"):
            marks = {"met": "ok", "failed": "bad", "unassessable": "warn"}
            tail.append(f"  {_mark(marks.get(v['ceilings'], 'warn'))} Ceilings: {v['ceilings']}")
        if v.get("report"):
            tail.append(f"  Report: {_plain_paths(str(v['report']))}")
        return [head, *stages, "", *tail, *_next(*v.get("next_steps", []))]
    if status == "dry_run":
        cmds = [
            f"    {_plain_paths(s['command'])}" for s in v.get("stages", []) if s.get("command")
        ]
        return [
            f"{_mark('todo')} {_style('Dry run: nothing was changed', bold=True)}",
            *stages,
            "",
            "  Commands that would run:",
            *cmds,
        ]
    if status == "waiting_for_human":
        lines = [
            f"{_mark('wait')} {_style('Waiting for a person', bold=True)}: the golden set is not frozen yet",
            *stages,
            "",
        ]
        for item in v.get("what_to_do", []):
            lines += _wrap_item(item)
        return lines
    reason = v.get("reason", "The run stopped.")
    stage = v.get("failed_stage")
    lines = [
        f"{_mark('bad')} {_style('ragkit run stopped' + (f' at {stage}' if stage else ''), bold=True)}",
        *stages,
    ]
    lines += _wrap(reason)
    if v.get("detail"):
        lines += ["  Details (--json for the full text):"] + _wrap(
            str(v["detail"]).strip().replace("\n", " ")[:300], "    "
        )
    return lines


def _blocked(v: dict, **_: Any) -> list[str]:
    reason = (
        v.get("reason")
        or v.get("error")
        or v.get("error_type")
        or "The command could not continue."
    )
    return [
        f"{_mark('bad')} {_style('Stopped', bold=True)}",
        *_wrap(reason),
        *_next("fix the point above and run the command again (add --json for details)."),
    ]


def _failure(v: dict, **_: Any) -> list[str]:
    title = str(v.get("status", "failed")).replace("_", " ")
    lines = [f"{_mark('bad')} {_style(title.capitalize(), bold=True)}"]
    for key in ("reason", "error", "error_type"):
        if v.get(key):
            lines += _wrap(v[key])
            break
    return lines


def _generic(v: dict, **_: Any) -> list[str]:
    status = str(v.get("status", "result"))
    good = status.startswith("VERIFIED") or status in {"completed", "not_run"}
    lines = [f"{_mark('ok' if good else 'warn')} {_style(status, bold=True)}"]
    for key, value in v.items():
        if key == "status" or isinstance(value, (dict, list)):
            continue
        lines.append(f"  {key}: {value}")
    return lines + _next("add --json for the full details.")


RENDERERS = {
    "smoke_passed": _smoke_passed, "smoke_failed": _smoke_failed,
    "VERIFIED local imports": _doctor, "VERIFIED local hashes": _corpus_inspect,
    "provenance_written": _provenance_written, "questions_imported": _imported,
    "candidates_written": _candidates, "review_valid": _review_valid, "frozen": _frozen,
    "initialised": _initialised, "init_partial": _init_partial,
    "adapter_ok": _adapter_ok, "adapter_failed": _adapter_failed,
    "blocked": _blocked,
    "invalid_predictions": _failure, "invalid_config": _failure, "failed": _failure,
    "report_failed": _failure, "comparison_failed": _failure,
}  # fmt: skip


def render(value: dict, *, wrote: str | None = None) -> str:
    """The readable form of a result. Unknown shapes still get a sensible summary."""
    if "stages" in value:
        fn = _run
    elif "metric_deltas" in value:
        fn = _comparison
    elif value.get("status") in {"completed", "completed_with_failures"} and "predictions" in value:
        fn = _predict
    elif value.get("status") == "completed" and "metrics" in value and "retrieval_mode" in value:
        fn = _evaluation
    elif "planned_call_count" in value:
        fn = _plan
    else:
        fn = RENDERERS.get(str(value.get("status")), _generic)
    return "\n".join(line for line in fn(value, wrote=wrote) if line is not None)


def emit(value: dict, *, wrote: str | None = None) -> None:
    if json_mode():
        typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))
    else:
        typer.echo(render(value, wrote=wrote))
