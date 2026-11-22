"""Local inspection, budget planning and DeepEval compatibility-spike commands."""

import contextlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import typer

from rag_eval_kit import __version__
from rag_eval_kit.adapters.files import read_jsonl
from rag_eval_kit.budget import BudgetLedger
from rag_eval_kit.config import JudgeConfig
from rag_eval_kit.evaluation import compare_runs, evaluate_lexical, evaluate_semantic
from rag_eval_kit.privacy import configure_local_runtime
from rag_eval_kit.reporting import markdown_report
from rag_eval_kit.revision import verify_revision

app = typer.Typer(
    no_args_is_help=True,
    help="Local RAG evaluation toolkit — offline checks and bounded judge spike.",
)


def emit(value: dict) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _read_run(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read run file ({type(error).__name__})") from None
    if not isinstance(value, dict) or not (
        isinstance(value.get("per_question"), dict) or isinstance(value.get("metric_deltas"), dict)
    ):
        raise ValueError("Run or comparison file has an invalid schema")
    return value


def _write_text_exclusive(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


@app.command()
def doctor(
    builder: Annotated[Path | None, typer.Option(help="Optional builder repository root.")] = None,
    target_revision: Annotated[str | None, typer.Option(help="Required with --builder.")] = None,
) -> None:
    """Check local dependencies and an optional clean target; makes no API calls."""
    configure_local_runtime()
    try:
        from rag_eval_kit.spike import versions

        result = {
            "status": "VERIFIED local imports",
            "versions": versions(),
            "package_version": __version__,
            "provider_connectivity": "UNVERIFIED",
            "judge_key_configured": bool(os.getenv("RAGKIT_OPENAI_API_KEY")),
            "telemetry": "disabled",
            "paid_calls": 0,
        }
        if bool(builder) != bool(target_revision):
            raise ValueError("--builder and --target-revision must be supplied together")
        if builder and target_revision:
            result["target"] = verify_revision(builder, target_revision)
        emit(result)
    except Exception as error:
        emit({"status": "failed", "error_type": type(error).__name__})
        raise typer.Exit(1) from None


@app.command()
def plan(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    questions: Annotated[int, typer.Option(min=1, max=1000)] = 10,
    calls_per_question: Annotated[int, typer.Option(min=1, max=1000)] = 20,
) -> None:
    """Compute a conservative judge-only pilot allowance from explicit rates; no API calls."""
    try:
        settings = JudgeConfig.from_path(config)
    except Exception as error:
        emit({"status": "invalid_config", "error_type": type(error).__name__})
        raise typer.Exit(1) from None
    calls = questions * calls_per_question + 1
    reserve = settings.price.cost(settings.input_token_cap, settings.max_output_tokens)
    emit(
        {
            "status": "ESTIMATE, not measured spend or approved pilot",
            "model": settings.model,
            "questions": questions,
            "assumed_calls_per_question": calls_per_question,
            "availability_check_calls": 1,
            "planned_call_count": calls,
            "input_token_ceiling": calls * settings.input_token_cap,
            "output_token_ceiling": calls * settings.max_output_tokens,
            "judge_reservation_ceiling_usd": str(calls * reserve),
            "configured_spike_call_limit": settings.max_calls,
            "spike_reservation_ceiling_usd": str(settings.max_calls * reserve),
            "price_provenance": settings.price.model_dump(mode="json"),
            "excluded": [
                "builder generation",
                "builder embeddings",
                "dataset synthesis",
                "hosting",
            ],
            "excluded_cost_status": "UNVERIFIED; need separate rates and usage bounds",
            "model_availability": "UNVERIFIED until an approved minimal paid call succeeds",
        }
    )


@app.command()
def spike(
    live: Annotated[
        bool, typer.Option("--live", help="Use the paid judge, never default.")
    ] = False,
    approve_paid: Annotated[
        bool, typer.Option("--approve-paid", help="Operator approval.")
    ] = False,
    config: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    output: Annotated[Path | None, typer.Option(dir_okay=False, help="New report path.")] = None,
    budget_usd: Annotated[
        str | None,
        typer.Option(
            "--budget-usd",
            help="Per-run USD cap; overrides RAGKIT_BUDGET_USD when supplied.",
        ),
    ] = None,
) -> None:
    """Run 3 fixtures through 5 DeepEval metrics and Synthesizer; not a RAG benchmark."""
    configure_local_runtime()
    settings = None
    ledger = None
    key = None
    if live:
        if not approve_paid or config is None or output is None:
            emit(
                {
                    "status": "blocked",
                    "reason": "Live calls require --approve-paid, --config and a NEW --output path",
                }
            )
            raise typer.Exit(2)
        try:
            settings = JudgeConfig.from_path(config)
            limit_value = (
                budget_usd if budget_usd is not None else os.environ.get("RAGKIT_BUDGET_USD", "0")
            )
            limit = Decimal(limit_value)
            ledger = BudgetLedger(limit, settings.max_calls)
            key = os.environ.get("RAGKIT_OPENAI_API_KEY", "").strip()
            if not key:
                raise ValueError("Judge key missing")
        except (ValueError, InvalidOperation, OSError):
            emit(
                {
                    "status": "blocked",
                    "reason": (
                        "Valid config, positive per-run budget "
                        "and RAGKIT_OPENAI_API_KEY are required"
                    ),
                }
            )
            raise typer.Exit(2) from None
    elif approve_paid or config or budget_usd is not None:
        emit(
            {
                "status": "blocked",
                "reason": (
                    "Paid options require --live; omit --approve-paid, --config and "
                    "--budget-usd for offline fixtures"
                ),
            }
        )
        raise typer.Exit(2)

    report: dict = {
        "run_id": str(uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "tool_version": version("rag-eval-kit"),
        "builder_called": False,
        "target_revision": None,
        "requested_budget_usd": str(ledger.limit) if ledger else None,
    }
    handle = None
    judge = None

    def persist() -> None:
        if ledger:
            report["budget"] = ledger.snapshot()
        if handle:
            handle.seek(0)
            json.dump(report, handle, indent=2, default=str)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())

    try:
        if output:
            # Exclusive creation prevents accidental overwrite or reuse of a previous run's budget.
            handle = output.open("x", encoding="utf-8")
        if ledger:
            ledger.on_change = persist
            report["judge_config"] = settings.model_dump(mode="json")
        persist()
        from rag_eval_kit.spike import run_spike

        if live:
            from rag_eval_kit.judge import BudgetedOpenAIJudge

            judge = BudgetedOpenAIJudge(settings, ledger, key)
        else:
            from rag_eval_kit.offline import OfflineSchemaJudge

            judge = OfflineSchemaJudge()
        with contextlib.redirect_stdout(sys.stderr):
            run_spike(judge, offline=not live, progress=report)
        report["status"] = "completed"
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["error"] = (
            "No automatic retry. Inspect local configuration and budget; provider payload withheld."
        )
    finally:
        if live and judge is not None:
            judge.close()
        report["finished_at"] = datetime.now(UTC).isoformat()
        if not live:
            report["paid_calls"] = 0
        persist()
        if handle:
            handle.close()
    emit(report)
    if report["status"] != "completed":
        raise typer.Exit(1)


@app.command()
def evaluate(
    predictions: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False, help="New run JSON file.")],
    target_revision: Annotated[str, typer.Option()],
    dataset_hash: Annotated[str, typer.Option()],
    corpus_hash: Annotated[str, typer.Option()],
    retrieval_mode: Annotated[Literal["lexical", "semantic"], typer.Option()],
    target_repo: Annotated[
        Path | None, typer.Option(help="Optional local Git target to require clean exact HEAD.")
    ] = None,
    allow_unverified_target: Annotated[
        bool,
        typer.Option(
            "--allow-unverified-target",
            help="Accept a caller-supplied revision when no local target repo exists.",
        ),
    ] = False,
    live: Annotated[bool, typer.Option("--live", help="Run paid DeepEval judge metrics.")] = False,
    approve_paid: Annotated[bool, typer.Option("--approve-paid")] = False,
    config: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    budget_usd: Annotated[
        str | None,
        typer.Option("--budget-usd", help="Per-run USD cap; otherwise use RAGKIT_BUDGET_USD."),
    ] = None,
    repeats: Annotated[int, typer.Option(min=1, max=5)] = 3,
) -> None:
    """Score portable JSONL predictions; lexical is offline, semantic is paid and opt-in."""
    configure_local_runtime()
    if not re.fullmatch(r"[a-f0-9]{64}", dataset_hash) or not re.fullmatch(
        r"[a-f0-9]{64}", corpus_hash
    ):
        emit({"status": "blocked", "reason": "Dataset and corpus hashes must be SHA-256 hex"})
        raise typer.Exit(2)
    if target_repo is not None:
        try:
            target_check = verify_revision(target_repo, target_revision)
        except Exception as error:
            emit({"status": "blocked", "error_type": type(error).__name__})
            raise typer.Exit(2) from None
    else:
        if not allow_unverified_target:
            emit(
                {
                    "status": "blocked",
                    "reason": (
                        "A clean exact-revision Git target is required; otherwise pass "
                        "--allow-unverified-target explicitly"
                    ),
                }
            )
            raise typer.Exit(2)
        target_check = {
            "requested_revision": target_revision,
            "working_tree": "UNVERIFIED; explicit override",
        }

    if retrieval_mode == "semantic":
        if not live or not approve_paid or config is None:
            emit(
                {
                    "status": "blocked",
                    "reason": (
                        "Semantic evaluation requires --live, --approve-paid and --config; "
                        "it makes paid judge calls"
                    ),
                }
            )
            raise typer.Exit(2)
    elif live or approve_paid or config is not None or budget_usd is not None:
        emit(
            {
                "status": "blocked",
                "reason": "Judge options apply only to semantic evaluation",
            }
        )
        raise typer.Exit(2)

    try:
        records = read_jsonl(predictions)
    except Exception as error:
        emit({"status": "invalid_predictions", "error_type": type(error).__name__})
        raise typer.Exit(2) from None

    settings = None
    ledger = None
    judge = None
    key = None
    if live:
        try:
            settings = JudgeConfig.from_path(config)
            cap = budget_usd if budget_usd is not None else os.environ.get("RAGKIT_BUDGET_USD", "0")
            ledger = BudgetLedger(Decimal(cap), settings.max_calls)
            key = os.environ.get("RAGKIT_OPENAI_API_KEY", "").strip()
            if not key:
                raise ValueError("Judge key missing")
        except (ValueError, InvalidOperation, OSError):
            emit(
                {
                    "status": "blocked",
                    "reason": "Valid price config, positive budget and judge key are required",
                }
            )
            raise typer.Exit(2) from None

    report: dict = {
        "run_id": str(uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "target_check": target_check,
        "target_revision": target_revision,
        "requested_budget_usd": str(ledger.limit) if ledger else None,
    }
    handle = None

    def persist() -> None:
        if ledger:
            report["budget"] = ledger.snapshot()
        if handle:
            handle.seek(0)
            json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())

    try:
        handle = output.open("x", encoding="utf-8")
        persist()
        if live:
            ledger.on_change = persist
            from rag_eval_kit.judge import BudgetedOpenAIJudge

            judge = BudgetedOpenAIJudge(settings, ledger, key)
            run = evaluate_semantic(
                records,
                target_revision=target_revision,
                dataset_hash=dataset_hash,
                corpus_hash=corpus_hash,
                judge=judge,
                repeats=repeats,
            )
        else:
            run = evaluate_lexical(
                records,
                target_revision=target_revision,
                dataset_hash=dataset_hash,
                corpus_hash=corpus_hash,
            )
        run["target_check"] = target_check
        if target_check["working_tree"] != "clean":
            run.setdefault("warnings", []).append(
                "Target revision was caller-supplied and its repository state was not verified."
            )
        report.clear()
        report.update(run)
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["error"] = "Evaluation failed; inspect local configuration and run ledger."
    finally:
        if judge is not None:
            judge.close()
        report["finished_at"] = datetime.now(UTC).isoformat()
        persist()
        if handle:
            handle.close()
    emit(report)
    if report["status"] != "completed":
        raise typer.Exit(1)


@app.command()
def compare(
    baseline: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    candidate: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Optional new JSON output.")
    ] = None,
    allow_incompatible: Annotated[
        bool, typer.Option("--allow-incompatible", help="Override run compatibility checks.")
    ] = False,
    pass_metric: Annotated[
        str | None, typer.Option(help="Optional metric used for paired pass/fail.")
    ] = None,
    pass_threshold: Annotated[float | None, typer.Option(min=0, max=1)] = None,
    bootstrap_samples: Annotated[int, typer.Option(min=100, max=100_000)] = 10_000,
    seed: Annotated[int, typer.Option()] = 2026,
) -> None:
    """Compare compatible runs using paired bootstrap and optional exact McNemar tests."""
    try:
        result = compare_runs(
            _read_run(baseline),
            _read_run(candidate),
            allow_incompatible=allow_incompatible,
            pass_metric=pass_metric,
            pass_threshold=pass_threshold,
            bootstrap_samples=bootstrap_samples,
            seed=seed,
        )
        if output:
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write("\n")
        emit(result)
    except Exception as error:
        emit(
            {"status": "comparison_failed", "error_type": type(error).__name__, "error": str(error)}
        )
        raise typer.Exit(1) from None


@app.command()
def report(
    run_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Optional new Markdown output.")
    ] = None,
) -> None:
    """Render a saved evaluation run as a concise Markdown report."""
    try:
        markdown = markdown_report(_read_run(run_file))
        if output:
            _write_text_exclusive(output, markdown)
        typer.echo(markdown)
    except Exception as error:
        emit({"status": "report_failed", "error_type": type(error).__name__})
        raise typer.Exit(1) from None


from rag_eval_kit.cli_workflow import register  # noqa: E402

register(app)

if __name__ == "__main__":
    app()
