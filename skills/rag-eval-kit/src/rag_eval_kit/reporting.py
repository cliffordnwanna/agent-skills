"""Human-readable output for saved evaluation runs."""

from typing import Any


def markdown_report(run: dict[str, Any]) -> str:
    if "metric_deltas" in run:
        return comparison_markdown_report(run)
    lines = [
        "# RAG evaluation report",
        "",
        f"- Run: `{run.get('run_id', 'unknown')}`",
        f"- Status: **{run.get('status', 'unknown')}**",
        f"- Retrieval mode: `{run.get('retrieval_mode', 'unknown')}`",
        f"- Target revision: `{run.get('target_revision', 'unknown')}`",
        f"- Dataset SHA-256: `{run.get('dataset_hash', 'unknown')}`",
        f"- Corpus SHA-256: `{run.get('corpus_hash', 'unknown')}`",
        f"- Judge: `{(run.get('judge') or {}).get('model', 'not used')}`",
        *([f"- Hit@k level: `{run['hit_level']}`"] if run.get("hit_level") else []),
        "",
        "## Results",
        "",
        "| Metric | Score | Assessed | Status |",
        "|---|---:|---:|---|",
    ]
    for name, result in run.get("metrics", {}).items():
        score = result.get("score")
        if score is None:
            rendered_score = "not assessable"
        elif result.get("repeat_spread_min") is not None:
            rendered_score = (
                f"{score:.4f} (range {result['repeat_spread_min']:.4f} to "
                f"{result['repeat_spread_max']:.4f})"
            )
        else:
            rendered_score = f"{score:.4f}"
        lines.append(
            f"| {name} | {rendered_score} | {result.get('assessed', 0)} | "
            f"{result.get('status', 'UNVERIFIED')} |"
        )
    counts = run.get("counts", {})
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Records: {counts.get('total_records', 0)}",
            f"- Valid records: {counts.get('valid_records', 0)}",
            f"- Invalid records: {counts.get('invalid_records', 0)}",
            f"- Unassessable records/questions: "
            f"{counts.get('unassessable_records', counts.get('unassessable_questions', 0))}",
        ]
    )
    invalid = run.get("invalid_records", [])
    if invalid:
        lines.extend(["", "## Invalid records", ""])
        lines.extend(
            f"- `{item['question_id']}` repeat {item['repeat']}: {item['reason']}"
            for item in invalid
        )
    unassessable = run.get("unassessable_records", [])
    if unassessable:
        lines.extend(["", "## Unassessable records", ""])
        lines.extend(
            f"- `{item['question_id']}` repeat {item['repeat']}: {item['reason']}"
            for item in unassessable
        )
    lines.extend(_operational_lines(run))
    budget = run.get("budget")
    if budget:
        lines.extend(
            [
                "",
                "## Judge budget",
                "",
                f"- Limit: ${budget.get('limit_usd', 'unknown')}",
                f"- Committed/reserved: ${budget.get('committed_or_reserved_usd', 'unknown')}",
                f"- Accounting status: "
                f"{budget.get('components', {}).get('judge', {}).get('status', 'UNVERIFIED')}",
            ]
        )
    warnings = run.get("warnings", [])
    if warnings:
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def _ms(value: Any) -> str:
    return "n/a" if value is None else f"{value:.1f} ms"


def _percent(value: Any) -> str:
    return "unknown" if value is None else f"{value * 100:.1f}%"


def _operational_lines(run: dict[str, Any]) -> list[str]:
    obs = run.get("observability")
    if not obs:
        return []
    lat, errors, invalid = obs["latency_ms"], obs["error_rate"], obs["invalid_rate"]
    lines = ["", "## Operational checks", ""]
    if lat.get("status") == "VERIFIED":
        small = " (small sample: p95 is close to the slowest answer)" if lat["low_sample"] else ""
        lines.append(
            f"- Latency, client-side, answered questions: p50 {_ms(lat['p50'])}, "
            f"p95 {_ms(lat['p95'])}, max {_ms(lat['max'])}, n={lat['n']}{small}"
        )
    else:
        lines.append(f"- Latency: not available ({lat.get('reason', 'not recorded')})")
    app = obs["app_reported_latency_ms"]
    if app.get("status") == "VERIFIED":
        lines.append(
            f"- App-reported time: p50 {_ms(app['p50'])}, p95 {_ms(app['p95'])}, n={app['n']}"
        )
    if errors["status"] == "VERIFIED":
        lines.append(
            f"- Error rate: {_percent(errors['rate'])} ({errors['failed']} of "
            f"{errors['attempted']} questions failed, {errors['timeouts']} timeouts)"
        )
    else:
        lines.append(f"- Error rate: unknown ({errors['reason']})")
    lines.append(
        f"- Invalid rate: {_percent(invalid['rate'])} "
        f"({invalid['invalid']} of {invalid['total']} records)"
    )
    cost = obs["cost"]
    if cost["status"] in {"ESTIMATED", "PARTIAL"}:
        lines.append(
            f"- Estimated cost of the app under test: ${float(cost['per_query_usd']):.6f} per "
            f"query, ${float(cost['estimated_usd_total']):.6f} in total "
            f"({cost['status'].lower()}; {cost['note']})"
        )
    else:
        lines.append(f"- Estimated cost: unavailable ({cost['reason']})")
    lines.extend(f"- Warning: {w}" for w in obs.get("warnings", []))
    check = run.get("ceiling_check")
    if check:
        lines.extend(
            ["", "## Ceilings", "", f"Overall: **{check['overall']}**", ""]
            if check["checks"]
            else ["", "## Ceilings", "", "No ceilings were set.", ""]
        )
        if check["checks"]:
            lines.extend(["| Ceiling | Limit | Observed | Result |", "|---|---:|---:|---|"])
            for item in check["checks"]:
                observed = "not available" if item["observed"] is None else f"{item['observed']:g}"
                lines.append(
                    f"| {item['ceiling']} | {item['limit']:g} | {observed} | {item['result']} |"
                )
        lines.extend(f"- {note}" for note in check.get("notes", []))
    return lines


def comparison_markdown_report(comparison: dict[str, Any]) -> str:
    lines = [
        "# RAG run comparison",
        "",
        f"- Baseline run: `{comparison.get('baseline_run_id', 'unknown')}`",
        f"- Candidate run: `{comparison.get('candidate_run_id', 'unknown')}`",
        f"- Compatible: **{comparison.get('compatible', False)}**",
        f"- Compatibility override: **{comparison.get('compatibility_overridden', False)}**",
        f"- Paired questions: {comparison.get('paired_questions', 0)}",
        "",
        "## Paired metric deltas",
        "",
        "| Metric | Mean change | Paired questions | 95% paired bootstrap CI |",
        "|---|---:|---:|---:|",
    ]
    for name, result in comparison.get("metric_deltas", {}).items():
        delta = result.get("mean_delta")
        interval = result.get("bootstrap_95_ci")
        rendered_delta = "not assessable" if delta is None else f"{delta:+.4f}"
        rendered_interval = (
            "not assessable" if interval is None else f"[{interval[0]:+.4f}, {interval[1]:+.4f}]"
        )
        lines.append(
            f"| {name} | {rendered_delta} | {result.get('paired_questions', 0)} | "
            f"{rendered_interval} |"
        )
    paired_test = comparison.get("paired_pass_test")
    if paired_test:
        lines.extend(
            [
                "",
                "## Paired pass/fail",
                "",
                f"- Metric and threshold: `{paired_test['metric']}` >= {paired_test['threshold']}",
                f"- Exact two-sided McNemar p-value: {paired_test['mcnemar_exact_two_sided_p']}",
                f"- Baseline Wilson 95% CI: {paired_test['baseline_pass_rate_wilson_95_ci']}",
                f"- Candidate Wilson 95% CI: {paired_test['candidate_pass_rate_wilson_95_ci']}",
            ]
        )
    if comparison.get("compatibility_mismatches"):
        lines.extend(
            [
                "",
                "Compatibility differences: " + ", ".join(comparison["compatibility_mismatches"]),
            ]
        )
    if comparison.get("warnings"):
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {warning}" for warning in comparison["warnings"])
    lines.append("")
    return "\n".join(lines)
