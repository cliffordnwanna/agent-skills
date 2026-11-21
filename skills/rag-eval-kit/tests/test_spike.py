import json

from typer.testing import CliRunner

from rag_eval_kit.cli import app


def test_all_five_real_deepeval_metrics_and_synthesizer_run_without_network(tmp_path):
    path = tmp_path / "offline.json"
    result = CliRunner().invoke(app, ["spike", "--output", str(path)])
    assert result.exit_code == 0, result.output
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["paid_calls"] == 0
    assert report["model_compatibility"] == "UNVERIFIED"
    assert report["quality_evidence"] is False
    assert report["builder_called"] is False
    assert len(report["metrics"]) == 15
    assert len({item["metric"] for item in report["metrics"]}) == 5
    assert all(item["score"] is None for item in report["metrics"])
    assert report["synthesizer"]["candidate_count"] == 3
    assert all(not item["approved"] for item in report["synthesizer"]["candidates"])
    assert report["fixture_model_calls"] > 0
