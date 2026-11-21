import hashlib
import json

import httpx
import pytest

from rag_eval_kit.adapters.base import AdapterError
from rag_eval_kit.adapters.builder import BuilderHTTPAdapter, BuilderHTTPConfig
from rag_eval_kit.adapters.files import JSONLRecordError, read_jsonl, write_jsonl
from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig
from rag_eval_kit.models import (
    CorpusDocument,
    EvaluationCase,
    EvaluationRecord,
)


def case(**changes):
    data = {
        "question_id": "q-1",
        "question": "What does this API do?",
        "reference_answer": "It validates JSON request bodies.",
        "reference_evidence": ["FastAPI reads request bodies as JSON."],
        "expected_source_ids": ["body"],
        "category": "direct",
    }
    data.update(changes)
    return EvaluationCase.model_validate(data)


def record(**changes):
    data = {
        "question_id": "q-1",
        "question": "What does this API do?",
        "answer": "It validates JSON request bodies.",
        "retrieved_contexts": ["FastAPI reads request bodies as JSON."],
        "retrieved_source_ids": ["body"],
        "reference_answer": "It validates JSON request bodies.",
        "reference_evidence": ["FastAPI reads request bodies as JSON."],
        "target_revision": "a" * 40,
        "retrieval_mode": "semantic",
        "expected_source_ids": ["body"],
        "category": "direct",
    }
    data.update(changes)
    return EvaluationRecord.model_validate(data)


def corpus():
    return [
        CorpusDocument(
            source_id="body",
            title="Request bodies",
            content="FastAPI reads request bodies as JSON.",
            source_url="https://example.test/body",
            source_path="body.md",
            source_sha256="b" * 64,
            content_sha256="c" * 64,
        )
    ]


def test_jsonl_round_trip_preserves_full_retrieved_contexts(tmp_path):
    path = tmp_path / "records.jsonl"
    expected = record()
    write_jsonl(path, [expected])
    assert read_jsonl(path) == [expected]
    assert json.loads(path.read_text(encoding="utf-8"))["retrieved_contexts"] == [
        "FastAPI reads request bodies as JSON."
    ]


@pytest.mark.parametrize(
    "content, error",
    [
        ('{"question_id":"x"}\n', "Invalid evaluation record at line 1"),
        (" \n", "Blank JSONL line at 1"),
    ],
)
def test_jsonl_rejects_bad_rows_without_echoing_content(tmp_path, content, error):
    path = tmp_path / "bad.jsonl"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(JSONLRecordError, match=error):
        read_jsonl(path)


def test_jsonl_rejects_duplicate_question_and_repeat(tmp_path):
    path = tmp_path / "duplicate.jsonl"
    path.write_text(
        record().model_dump_json() + "\n" + record().model_dump_json() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(JSONLRecordError, match="Duplicate question_id/repeat"):
        read_jsonl(path)


def test_jsonl_writer_checks_before_creating_output(tmp_path):
    path = tmp_path / "duplicate.jsonl"
    with pytest.raises(JSONLRecordError):
        write_jsonl(path, [record(), record()])
    assert not path.exists()


def test_generic_http_adapter_maps_configured_response_fields_and_env_header(
    monkeypatch,
):
    monkeypatch.setenv("RAG_TEST_TOKEN", "secret-fixture")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "answer": "A verified answer",
                    "contexts": ["full retrieved text"],
                    "sources": ["source-1"],
                    "mode": "semantic",
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = GenericHTTPConfig(
        base_url="https://rag.example.test/v1",
        endpoint="answer",
        question_field="query",
        question_id_field="id",
        answer_path="data.answer",
        contexts_path="data.contexts",
        source_ids_path="data.sources",
        retrieval_mode_path="data.mode",
        headers={"Authorization": "Bearer ${ENV:RAG_TEST_TOKEN}"},
    )
    with GenericHTTPAdapter(config, client) as adapter:
        result = adapter.predict(case(), "b" * 40)
    assert result.answer == "A verified answer"
    assert result.retrieved_contexts == ["full retrieved text"]
    assert result.retrieved_source_ids == ["source-1"]
    assert result.retrieval_mode == "semantic"
    assert seen == {
        "url": "https://rag.example.test/v1/answer",
        "body": {"query": "What does this API do?", "id": "q-1"},
        "auth": "Bearer secret-fixture",
    }


def test_generic_http_rejects_unknown_mode_and_http_error():
    unknown_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "answer": "a",
                    "retrieved_contexts": [],
                    "retrieved_source_ids": [],
                    "retrieval_mode": "maybe",
                },
            )
        )
    )
    with GenericHTTPAdapter(
        GenericHTTPConfig(base_url="https://rag.example.test"), unknown_client
    ) as adapter:
        with pytest.raises(AdapterError, match="unknown retrieval mode"):
            adapter.predict(case(), "c" * 40)

    error_client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="private details"))
    )
    with GenericHTTPAdapter(
        GenericHTTPConfig(base_url="https://rag.example.test"), error_client
    ) as adapter:
        with pytest.raises(AdapterError, match="status 503") as caught:
            adapter.predict(case(), "c" * 40)
    assert "private details" not in str(caught.value)


def test_builder_adapter_uses_fresh_sessions_and_cleans_up():
    requests = []
    session_ids = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"mode": "live"})
        if request.method == "PUT":
            session_ids.append(body["sessionId"])
            return httpx.Response(200, json={"success": True})
        if request.url.path == "/api/chat":
            assert body["sessionId"] in session_ids
            return httpx.Response(
                200,
                json={
                    "reply": "The answer.",
                    "chunks": [
                        {
                            "preview": "Full source chunk text",
                            "knowledgeId": "body",
                        }
                    ],
                    "retrievalMode": "semantic",
                    "analytics": {"totalTokens": 12},
                },
            )
        return httpx.Response(200, json={"success": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with BuilderHTTPAdapter(BuilderHTTPConfig(base_url="http://builder.local"), client) as adapter:
        first = adapter.predict(case(), corpus(), "d" * 40)
        adapter.predict(case(question_id="q-2"), corpus(), "d" * 40)
    assert first.retrieved_contexts == ["Full source chunk text"]
    assert first.retrieved_source_ids == ["body"]
    assert first.retrieval_mode == "semantic"
    assert first.metadata["builder_usage_cost_status"].startswith("UNVERIFIED")
    assert len(set(session_ids)) == 2
    assert sum(path == "/api/knowledge" and method == "DELETE" for method, path, _ in requests) == 2


def test_builder_demo_mode_is_not_mislabeled_semantic():
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"mode": "demo"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with BuilderHTTPAdapter(BuilderHTTPConfig(base_url="http://builder.local"), client) as adapter:
        with pytest.raises(AdapterError, match="requires a live Builder"):
            adapter.predict(case(), corpus(), "e" * 40)
    assert requests == ["/api/health"]


@pytest.mark.parametrize("count, chars", [(21, 1), (3, 40000)])
def test_builder_adapter_enforces_corpus_caps(count, chars):
    documents = [
        CorpusDocument(
            source_id=f"s{index}",
            title=f"Source {index}",
            content="x" * chars,
            source_url=f"https://example.test/{index}",
            source_path=f"{index}.md",
            source_sha256=hashlib.sha256(b"source").hexdigest(),
            content_sha256=hashlib.sha256(b"content").hexdigest(),
        )
        for index in range(count)
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    with BuilderHTTPAdapter(BuilderHTTPConfig(base_url="http://builder.local"), client) as adapter:
        with pytest.raises(AdapterError, match="corpus|character"):
            adapter.predict(case(), documents, "f" * 40)


def test_corpus_document_schema_enforces_per_document_limit():
    with pytest.raises(ValueError):
        CorpusDocument(
            source_id="too-large",
            title="Oversized",
            content="x" * 50001,
            source_url="https://example.test/large",
            source_path="large.md",
            source_sha256="b" * 64,
            content_sha256="c" * 64,
        )
