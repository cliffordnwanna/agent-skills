"""corpus, dataset, predict and smoke commands; offline unless the target app is paid."""

import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Annotated, Literal

import typer

from rag_eval_kit.corpus import CorpusError, load_corpus
from rag_eval_kit.dataset import build_candidates, validate_candidates, write_candidate_files
from rag_eval_kit.freeze import ReviewError, freeze, load_review
from rag_eval_kit.own_data import (
    QuestionImportError,
    init_corpus,
    read_question_file,
)
from rag_eval_kit.pipeline import run_pipeline
from rag_eval_kit.predict import read_cases, run_predictions
from rag_eval_kit.scaffold import DEFAULT_SKILL_PARENT, InitError, copy_skill, write_starter_files


def _emit(value: dict) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _fail(reason: str, code: int = 2) -> None:
    _emit({"status": "blocked", "reason": reason})
    raise typer.Exit(code)


def register(app: typer.Typer) -> None:
    corpus_app = typer.Typer(help="Inspect a provenance-pinned corpus.", no_args_is_help=True)
    dataset_app = typer.Typer(
        help="Create, review and freeze the golden dataset.", no_args_is_help=True
    )
    app.add_typer(corpus_app, name="corpus")
    app.add_typer(dataset_app, name="dataset")
    adapter_app = typer.Typer(
        help="Check that ragkit can talk to your RAG app.", no_args_is_help=True
    )
    app.add_typer(adapter_app, name="adapter")

    @corpus_app.command("inspect")
    def corpus_inspect(
        directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    ) -> None:
        """Verify hashes and Builder size limits; print provenance. Makes no API calls."""
        try:
            manifest, docs, corpus_hash = load_corpus(directory)
        except CorpusError as error:
            _fail(str(error))
        total = sum(len(d.content) for d in docs)
        _emit(
            {
                "status": "VERIFIED local hashes",
                "name": manifest.name,
                "source_repository": manifest.source_repository,
                "source_revision": manifest.source_revision,
                "license": manifest.license,
                "corpus_sha256": corpus_hash,
                "documents": [
                    {"source_id": d.source_id, "characters": len(d.content)} for d in docs
                ],
                "total_characters": total,
                "builder_limits_ok": len(docs) <= 20 and total <= 100_000,
            }
        )

    @corpus_app.command("init")
    def corpus_init(
        directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
        name: Annotated[str, typer.Option(help="A short name for this document set.")],
        license_name: Annotated[
            str,
            typer.Option("--license", help="Licence of the documents, e.g. MIT or proprietary."),
        ],
        license_url: Annotated[
            str, typer.Option(help="Where the licence is stated (a URL, or a path or note).")
        ],
        source_repository: Annotated[
            str, typer.Option(help="Where the documents come from (a URL, path or note).")
        ],
        source_revision: Annotated[
            str | None,
            typer.Option(help="40-character commit SHA of this version. Default: git HEAD."),
        ] = None,
    ) -> None:
        """Write provenance.json for your own .md and .txt files. Never overwrites. No network."""
        try:
            info = init_corpus(
                directory,
                name=name,
                license_name=license_name,
                license_url=license_url,
                source_repository=source_repository,
                source_revision=source_revision,
            )
        except (CorpusError, OSError) as error:
            _fail(str(error))
        _emit({"status": "provenance_written", **info})

    @dataset_app.command("import")
    def dataset_import(
        questions: Annotated[
            Path,
            typer.Argument(
                exists=True,
                dir_okay=False,
                help="Your questions: .jsonl, or .csv in review format.",
            ),
        ],
        corpus_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)],
        output_dir: Annotated[Path, typer.Option(file_okay=False, help="Review files go here.")],
    ) -> None:
        """Bring your own questions. Checks them against the corpus; a person must still approve."""
        try:
            cases = read_question_file(questions)
            _, docs, _ = load_corpus(corpus_dir)
            validate_candidates(cases, docs)
            info = write_candidate_files(cases, output_dir)
        except FileExistsError:
            _fail("Output files already exist; imports never overwrite. Use a new --output-dir")
        except (CorpusError, QuestionImportError, ValueError, OSError) as error:
            _fail(str(error))
        _emit(
            {
                "status": "questions_imported",
                "review_required": True,
                "next_step": "A person fills the keep column (yes/no) of review.csv, "
                "then runs dataset review and dataset freeze.",
                **info,
            }
        )

    @dataset_app.command("generate")
    def dataset_generate(
        corpus_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)],
        output_dir: Annotated[Path, typer.Option(file_okay=False)],
    ) -> None:
        """Write the built-in FastAPI candidate set for review. No model call; not approved data."""
        try:
            _, docs, _ = load_corpus(corpus_dir)
            candidates = build_candidates()
            validate_candidates(candidates, docs)
            info = write_candidate_files(candidates, output_dir)
        except (CorpusError, ValueError, OSError) as error:
            _fail(f"{type(error).__name__}: {error}")
        _emit({"status": "candidates_written", "review_required": True, **info})

    @dataset_app.command("review")
    def dataset_review(
        review_csv: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
        corpus_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    ) -> None:
        """Validate a filled review sheet (keep=yes/no on every row). Writes nothing."""
        try:
            _, docs, _ = load_corpus(corpus_dir)
            _, summary = load_review(review_csv, docs)
        except (CorpusError, ReviewError) as error:
            _fail(str(error))
        _emit({"status": "review_valid", **summary})

    @dataset_app.command("freeze")
    def dataset_freeze(
        review_csv: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
        corpus_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)],
        output_dir: Annotated[Path, typer.Option(file_okay=False, help="Must not exist.")],
        approved_by: Annotated[str, typer.Option(help="Reviewer who approved the sheet.")],
        seed: Annotated[int, typer.Option()] = 20261121,
    ) -> None:
        """Freeze reviewed questions into golden/dev/held-out files with hashes."""
        if not approved_by.strip():
            _fail("--approved-by must name the human reviewer")
        if output_dir.exists():
            _fail("Output directory already exists; frozen datasets are never overwritten")
        try:
            _, docs, corpus_hash = load_corpus(corpus_dir)
            cases, _ = load_review(review_csv, docs)
            manifest = freeze(
                cases,
                output_dir,
                corpus_hash=corpus_hash,
                seed=seed,
                approved_by=approved_by.strip(),
                review_sheet_sha256=hashlib.sha256(review_csv.read_bytes()).hexdigest(),
            )
        except (CorpusError, ReviewError) as error:
            _fail(str(error))
        _emit({"status": "frozen", **manifest})

    @app.command()
    def predict(
        dataset: Annotated[
            Path, typer.Argument(exists=True, dir_okay=False, help="dev/heldout.jsonl")
        ],
        adapter: Annotated[Literal["generic", "builder"], typer.Option()],
        adapter_config: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
        target_revision: Annotated[str, typer.Option(help="Exact revision of the system tested.")],
        output: Annotated[Path, typer.Option(dir_okay=False, help="New predictions JSONL.")],
        corpus_dir: Annotated[Path | None, typer.Option(file_okay=False)] = None,
        semantic: Annotated[
            bool, typer.Option(help="Builder only: require live semantic mode.")
        ] = False,
        concurrency: Annotated[int, typer.Option(min=1, max=5)] = 1,
    ) -> None:
        """Ask the target app every question and write portable predictions; failures are listed."""
        from rag_eval_kit.adapters.builder import BuilderHTTPAdapter, BuilderHTTPConfig
        from rag_eval_kit.adapters.files import write_jsonl
        from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig

        try:
            cases = read_cases(dataset)
            raw = json.loads(adapter_config.read_text(encoding="utf-8"))
            if adapter == "builder":
                if corpus_dir is None:
                    _fail("--corpus-dir is required for the builder adapter")
                _, docs, _ = load_corpus(corpus_dir)
                client = BuilderHTTPAdapter(BuilderHTTPConfig(**raw))
                fn = lambda c: client.predict(  # noqa: E731
                    c, docs, target_revision, require_semantic=semantic
                )
            else:
                client = GenericHTTPAdapter(GenericHTTPConfig(**raw))
                fn = lambda c: client.predict(c, target_revision)  # noqa: E731
        except (CorpusError, ValueError, OSError) as error:
            _fail(f"{type(error).__name__}: {error}")
        try:
            records, failures = run_predictions(cases, fn, concurrency=concurrency)
        finally:
            client.close()
        if records:
            write_jsonl(output, records)
        _emit(
            {
                "status": "completed" if not failures else "completed_with_failures",
                "predictions": len(records),
                "failed": failures,
                "output": str(output) if records else None,
            }
        )
        if failures:
            raise typer.Exit(1)

    @app.command("init")
    def init_command(
        directory: Annotated[
            Path, typer.Option(file_okay=False, help="Where to write the starter files.")
        ] = Path("."),
        skill_dir: Annotated[
            Path | None,
            typer.Option(
                file_okay=False,
                help="Copy the agent skill into this skills folder. Giving this is your consent.",
            ),
        ] = None,
        no_skill: Annotated[
            bool, typer.Option("--no-skill", help="Do not ask about the agent skill.")
        ] = False,
    ) -> None:
        """Write a starter ragkit.yaml and adapter.json. Never overwrites. Skill is optional."""
        try:
            written = write_starter_files(directory)
        except (InitError, OSError) as error:
            _fail(str(error))
        skill_info: dict = {"copied": False}
        try:
            chosen = skill_dir
            if chosen is None and not no_skill:
                try:
                    wants = typer.confirm(
                        "Copy the rag-eval-kit agent skill into your agent's skills folder? "
                        "It is optional. Nothing is copied unless you say yes.",
                        default=False,
                        err=True,
                    )
                    if wants:
                        chosen = Path(
                            typer.prompt(
                                "Your agent's skills folder", default=DEFAULT_SKILL_PARENT, err=True
                            )
                        )
                except typer.Abort:
                    chosen = None  # no answer is a no
            if chosen is not None:
                skill_info = {"copied": True, "path": str(copy_skill(chosen))}
        except (InitError, OSError) as error:
            _emit({"status": "init_partial", "written": written, "skill_error": str(error)})
            raise typer.Exit(2) from None
        _emit(
            {
                "status": "initialised",
                "written": written,
                "skill": skill_info,
                "next_steps": [
                    "Edit adapter.json to match your app, then: "
                    "ragkit adapter test --adapter-config adapter.json",
                    "Put your documents in a folder and run: ragkit corpus init <folder> ...",
                    "Bring your questions: ragkit dataset import ... "
                    "(a person must then approve them)",
                    "Edit ragkit.yaml, then run: ragkit run",
                ],
            }
        )

    @adapter_app.command("test")
    def adapter_test(
        adapter_config: Annotated[
            Path,
            typer.Option(exists=True, dir_okay=False, help="Generic HTTP adapter config JSON."),
        ],
        question: Annotated[
            str, typer.Option(help="The question to send.")
        ] = "What is this system for?",
        dataset: Annotated[
            Path | None,
            typer.Option(
                exists=True, dir_okay=False, help="Send this file's first question instead."
            ),
        ] = None,
    ) -> None:
        """Send ONE question to your app and show what ragkit extracted. Saves nothing."""
        from rag_eval_kit.adapters.base import AdapterError
        from rag_eval_kit.adapters.generic_http import (
            GenericHTTPAdapter,
            GenericHTTPConfig,
            build_payload,
            url_for,
        )
        from rag_eval_kit.models import EvaluationCase

        try:
            config = GenericHTTPConfig(**json.loads(adapter_config.read_text(encoding="utf-8")))
            case = (
                read_cases(dataset)[0]
                if dataset
                else EvaluationCase(
                    question_id="adapter-test",
                    question=question,
                    reference_answer="not used",
                    category="direct",
                )
            )
        except (ValueError, OSError) as error:
            _fail(f"{type(error).__name__}: {error}")
        shown_url = url_for(config).split("?")[0]
        sent = build_payload(config, case)
        base = {"url": shown_url, "sent": sent}
        with GenericHTTPAdapter(config) as adapter:
            started = time.perf_counter()
            try:
                body = adapter.fetch(case)
            except AdapterError as error:
                _emit(
                    {"status": "adapter_failed", "stage": "request", "reason": str(error), **base}
                )
                raise typer.Exit(2) from None
            latency = round((time.perf_counter() - started) * 1000, 1)
            keys = sorted(body) if isinstance(body, dict) else f"(a {type(body).__name__})"
            try:
                record = adapter.parse(case, body, "adapter-test")
            except AdapterError as error:
                _emit(
                    {
                        "status": "adapter_failed",
                        "stage": "read_response",
                        "reason": str(error),
                        "response_top_level_keys": keys,
                        "hint": "Fix answer_path, contexts_path, source_ids_path or "
                        "retrieval_mode_path so they match these keys.",
                        **base,
                    }
                )
                raise typer.Exit(2) from None
        _emit(
            {
                "status": "adapter_ok",
                "latency_ms": latency,
                "response_top_level_keys": keys,
                "extracted": {
                    "answer": record.answer[:300],
                    "retrieved_contexts": [c[:200] for c in record.retrieved_contexts[:3]],
                    "retrieved_context_count": len(record.retrieved_contexts),
                    "retrieved_source_ids": record.retrieved_source_ids,
                    "retrieval_mode": record.retrieval_mode,
                    "abstained": record.abstained,
                },
                "note": "One real request was sent to your endpoint. Nothing was saved.",
                **base,
            }
        )

    @app.command("run")
    def run_command(
        config: Annotated[
            Path, typer.Option("--config", help="Settings file.", dir_okay=False)
        ] = Path("ragkit.yaml"),
        split: Annotated[Literal["dev", "heldout"], typer.Option()] = "dev",
        confirm_heldout: Annotated[
            bool, typer.Option(help="Required for --split heldout: it is for one final run.")
        ] = False,
        dry_run: Annotated[
            bool, typer.Option(help="Show the commands that would run; change nothing.")
        ] = False,
    ) -> None:
        """Run the free offline pipeline from ragkit.yaml. Stops at human steps; resumes."""
        summary = run_pipeline(
            config, split=split, confirm_heldout=confirm_heldout, dry_run=dry_run
        )
        _emit(summary)
        if summary["status"] == "blocked":
            raise typer.Exit(2)

    @app.command()
    def smoke() -> None:
        """End-to-end offline check: local mock RAG server -> adapter -> lexical metrics."""
        from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig
        from rag_eval_kit.evaluation import evaluate_lexical
        from rag_eval_kit.mock_server import (
            DEMO_DOCS,
            demo_cases,
            make_server,
            serve_in_thread,
        )

        server = make_server()
        serve_in_thread(server)
        try:
            config = GenericHTTPConfig(base_url=f"http://127.0.0.1:{server.server_address[1]}")
            with GenericHTTPAdapter(config) as adapter:
                records, failures = run_predictions(
                    demo_cases(), lambda c: adapter.predict(c, "smoke-demo")
                )
        finally:
            server.shutdown()
            server.server_close()
        if failures:
            _emit({"status": "smoke_failed", "failed": failures})
            raise typer.Exit(1)
        fingerprint = hashlib.sha256(json.dumps(DEMO_DOCS, sort_keys=True).encode()).hexdigest()
        with tempfile.TemporaryDirectory():
            run = evaluate_lexical(
                records,
                target_revision="smoke-demo",
                dataset_hash=fingerprint,
                corpus_hash=fingerprint,
            )
        _emit({"status": "smoke_passed", "paid_calls": 0, "result": run})
