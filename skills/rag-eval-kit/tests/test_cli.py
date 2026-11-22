import json
from datetime import date

import pytest
from typer.testing import CliRunner

from rag_eval_kit.adapters.files import write_jsonl
from rag_eval_kit.cli import app
from rag_eval_kit.config import JudgeConfig
from rag_eval_kit.models import EvaluationRecord

runner = CliRunner()


def write_config(path):
    path.write_text(
        json.dumps(
            {
                "model": "fixture-model",
                "price": {
                    "input_usd_per_million": 1,
                    "output_usd_per_million": 2,
                    "source_url": "https://example.test/rates",
                    "checked_on": date.today().isoformat(),
                },
            }
        ),
        encoding="utf-8",
    )


def test_help_exposes_only_implemented_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "doctor",
        "plan",
        "spike",
        "evaluate",
        "compare",
        "report",
        "predict",
        "smoke",
        "corpus",
        "dataset",
    ):
        assert command in result.output
    spike_help = runner.invoke(app, ["spike", "--help"])
    assert "--budget-usd" in spike_help.output


def test_doctor_is_offline_and_does_not_claim_model_availability():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["provider_connectivity"] == "UNVERIFIED"
    assert data["paid_calls"] == 0
    assert data["versions"]["deepeval"] == "4.3.4"


def test_doctor_requires_revision_with_path(tmp_path):
    result = runner.invoke(app, ["doctor", "--builder", str(tmp_path)])
    assert result.exit_code == 1


@pytest.mark.parametrize("args", [["--live"], ["--live", "--approve-paid"], ["--approve-paid"]])
def test_live_requires_explicit_approval_config_budget_and_key(args):
    result = runner.invoke(app, ["spike", *args])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "blocked"


def test_budget_option_is_rejected_for_offline_run():
    result = runner.invoke(app, ["spike", "--budget-usd", "1"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "blocked"


def test_missing_budget_blocks_before_creating_report(tmp_path, monkeypatch):
    config = tmp_path / "judge.json"
    write_config(config)
    monkeypatch.setenv("RAGKIT_OPENAI_API_KEY", "test-fixture")
    monkeypatch.delenv("RAGKIT_BUDGET_USD", raising=False)
    output = tmp_path / "report.json"
    result = runner.invoke(
        app, ["spike", "--live", "--approve-paid", "--config", str(config), "--output", str(output)]
    )
    assert result.exit_code == 2
    assert not output.exists()


def test_per_run_budget_option_overrides_environment_without_network(tmp_path, monkeypatch):
    from rag_eval_kit import spike as spike_module

    config = tmp_path / "judge.json"
    write_config(config)
    monkeypatch.setenv("RAGKIT_OPENAI_API_KEY", "test-fixture")
    monkeypatch.setenv("RAGKIT_BUDGET_USD", "0.50")
    observed = {}

    def fake_run_spike(judge, offline, progress):
        observed["budget"] = str(judge.ledger.limit)
        observed["model"] = judge.config.model
        observed["offline"] = offline
        return progress

    monkeypatch.setattr(spike_module, "run_spike", fake_run_spike)
    output = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "spike",
            "--live",
            "--approve-paid",
            "--config",
            str(config),
            "--output",
            str(output),
            "--budget-usd",
            "0.25",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert observed == {
        "budget": "0.25",
        "model": "fixture-model",
        "offline": False,
    }
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["requested_budget_usd"] == "0.25"


def test_invalid_per_run_budget_blocks_before_creating_report(tmp_path, monkeypatch):
    config = tmp_path / "judge.json"
    write_config(config)
    monkeypatch.setenv("RAGKIT_OPENAI_API_KEY", "test-fixture")
    output = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "spike",
            "--live",
            "--approve-paid",
            "--config",
            str(config),
            "--output",
            str(output),
            "--budget-usd",
            "not-a-number",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "blocked"
    assert not output.exists()


def test_budget_plan_is_computed_from_explicit_rates_without_calls(tmp_path):
    path = tmp_path / "judge.json"
    write_config(path)
    result = runner.invoke(app, ["plan", "--config", str(path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["planned_call_count"] == 201
    assert data["judge_reservation_ceiling_usd"] == "4.431648"
    assert "builder embeddings" in data["excluded"]


def test_invalid_or_unknown_prices_fail_instead_of_becoming_free(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"model":"fixture-model","price":null}')
    result = runner.invoke(app, ["plan", "--config", str(path)])
    assert result.exit_code == 1
    with pytest.raises(ValueError):
        JudgeConfig.from_path(path)


def test_existing_report_is_never_overwritten(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("do not overwrite", encoding="utf-8")
    result = runner.invoke(app, ["spike", "--output", str(path)])
    assert result.exit_code == 1
    assert path.read_text() == "do not overwrite"


def test_offline_evaluate_writes_run_file_without_paid_calls(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    write_jsonl(
        predictions,
        [
            EvaluationRecord(
                question_id="q1",
                question="Question?",
                answer="Answer.",
                retrieved_contexts=["Context."],
                retrieved_source_ids=["source"],
                reference_answer="Answer.",
                reference_evidence=["Context."],
                expected_source_ids=["source"],
                category="direct",
                abstained=False,
                target_revision="a" * 40,
                retrieval_mode="lexical",
            )
        ],
    )
    output = tmp_path / "run.json"
    result = runner.invoke(
        app,
        [
            "evaluate",
            str(predictions),
            "--output",
            str(output),
            "--target-revision",
            "a" * 40,
            "--allow-unverified-target",
            "--dataset-hash",
            "b" * 64,
            "--corpus-hash",
            "c" * 64,
            "--retrieval-mode",
            "lexical",
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["status"] == "completed"
    assert data["metrics"]["hit_at_1"]["score"] == 1
    assert data["judge"] is None


def test_semantic_evaluation_requires_explicit_paid_approval(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text("{}", encoding="utf-8")
    output = tmp_path / "run.json"
    result = runner.invoke(
        app,
        [
            "evaluate",
            str(predictions),
            "--output",
            str(output),
            "--target-revision",
            "a" * 40,
            "--allow-unverified-target",
            "--dataset-hash",
            "b" * 64,
            "--corpus-hash",
            "c" * 64,
            "--retrieval-mode",
            "semantic",
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "blocked"
    assert not output.exists()
