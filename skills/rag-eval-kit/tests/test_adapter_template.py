"""Request templates for the generic HTTP adapter, and `ragkit adapter test`."""

import json

import httpx
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rag_eval_kit.adapters.generic_http import (
    GenericHTTPAdapter,
    GenericHTTPConfig,
    build_payload,
    fill_template,
)
from rag_eval_kit.cli import app
from rag_eval_kit.mock_server import demo_cases, make_server, serve_in_thread

runner = CliRunner()
CASE = demo_cases()[0]


def config(**extra):
    return GenericHTTPConfig(base_url="http://127.0.0.1:9", retry_backoff_seconds=0, **extra)


def test_default_payload_is_unchanged_without_a_template():
    assert build_payload(config(), CASE) == {"question": CASE.question}
    with_id = config(question_field="q", question_id_field="id")
    assert build_payload(with_id, CASE) == {"q": CASE.question, "id": CASE.question_id}


def test_template_fills_nested_values_and_leaves_other_values_alone():
    template = {
        "messages": [{"role": "user", "content": "Q: ${question}"}],
        "meta": {"id": "${question_id}", "stream": False, "top_k": 3},
    }
    out = build_payload(config(request=template), CASE)
    assert out["messages"][0]["content"] == f"Q: {CASE.question}"
    assert out["meta"] == {"id": CASE.question_id, "stream": False, "top_k": 3}


def test_question_text_is_never_re_expanded():
    template = {"text": "${question}", "id": "${question_id}"}
    tricky = CASE.model_copy(update={"question": "what does ${question_id} mean?"})
    out = fill_template(template, {"question": tricky.question, "question_id": "X1"})
    assert out == {"text": "what does ${question_id} mean?", "id": "X1"}


@pytest.mark.parametrize(
    "template,message",
    [
        ({"text": "${quesion}"}, "Unknown placeholder"),
        ({"text": "no placeholder here"}, "must contain"),
        ({"text": "${ENV:SECRET}"}, "Unknown placeholder"),
        ({"id": "${question_id}"}, "must contain"),
    ],
)
def test_bad_templates_fail_when_the_config_loads(template, message):
    with pytest.raises(ValidationError, match=message):
        config(request=template)


def test_template_is_what_goes_over_the_wire():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {"reply": "Port 8080."},
                "ctx": ["The alpha service listens on port 8080"],
                "ids": ["alpha"],
                "mode": "lexical",
            },
        )

    cfg = config(
        request={"messages": [{"role": "user", "content": "${question}"}], "stream": False},
        answer_path="data.reply",
        contexts_path="ctx",
        source_ids_path="ids",
        retrieval_mode_path="mode",
    )
    with GenericHTTPAdapter(cfg, httpx.Client(transport=httpx.MockTransport(handler))) as adapter:
        record = adapter.predict(CASE, "rev")
    assert seen["body"] == {
        "messages": [{"role": "user", "content": CASE.question}],
        "stream": False,
    }
    assert record.answer == "Port 8080." and record.retrieved_source_ids == ["alpha"]


@pytest.fixture
def server():
    srv = make_server()
    serve_in_thread(srv)
    yield srv
    srv.shutdown()
    srv.server_close()


def write_config(tmp_path, server, **extra):
    path = tmp_path / "adapter.json"
    body = {"base_url": f"http://127.0.0.1:{server.server_address[1]}", **extra}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def run_test_command(path, *extra):
    result = runner.invoke(app, ["adapter", "test", "--adapter-config", str(path), *extra])
    return result, json.loads(result.stdout)


def test_adapter_test_shows_what_was_extracted(tmp_path, server):
    path = write_config(tmp_path, server)
    result, out = run_test_command(path, "--question", "Which port does the alpha service use?")
    assert result.exit_code == 0, result.output
    assert out["status"] == "adapter_ok"
    assert out["extracted"]["retrieved_source_ids"] == ["alpha"]
    assert out["extracted"]["retrieval_mode"] == "lexical"
    assert out["sent"] == {"question": "Which port does the alpha service use?"}
    assert "Nothing was saved" in out["note"]


def test_adapter_test_works_with_a_request_template(tmp_path, server):
    path = write_config(
        tmp_path, server, request={"question": "${question}", "extra": {"mode": "test"}}
    )
    result, out = run_test_command(path, "--question", "Which port does the alpha service use?")
    assert result.exit_code == 0, result.output
    assert out["sent"]["extra"] == {"mode": "test"}


def test_adapter_test_explains_a_wrong_response_path(tmp_path, server):
    path = write_config(tmp_path, server, answer_path="data.text")
    result, out = run_test_command(path)
    assert result.exit_code == 2
    assert out["status"] == "adapter_failed" and out["stage"] == "read_response"
    assert "data.text" in out["reason"]
    assert "answer" in out["response_top_level_keys"]  # names only, so the user can fix the path
    assert "retrieved_contexts" in out["response_top_level_keys"]


def test_adapter_test_reports_an_unreachable_target(tmp_path):
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps({"base_url": "http://127.0.0.1:9", "max_retries": 0}))
    result, out = run_test_command(path)
    assert result.exit_code == 2 and out["stage"] == "request"


def test_adapter_test_rejects_a_bad_template_before_sending(tmp_path, server):
    path = write_config(tmp_path, server, request={"text": "${typo}"})
    result, out = run_test_command(path)
    assert result.exit_code == 2 and out["status"] == "blocked"
    assert "Unknown placeholder" in out["reason"]


def test_adapter_test_uses_the_first_dataset_question(tmp_path, server):
    path = write_config(tmp_path, server)
    dataset = tmp_path / "dev.jsonl"
    dataset.write_text("".join(c.model_dump_json() + "\n" for c in demo_cases()), encoding="utf-8")
    result, out = run_test_command(path, "--dataset", str(dataset))
    assert result.exit_code == 0 and out["sent"]["question"] == demo_cases()[0].question
