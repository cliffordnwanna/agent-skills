"""HTTP adapter for the baseline Conversational Agent Builder protocol."""

import time
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from rag_eval_kit.adapters.base import AdapterError
from rag_eval_kit.models import CorpusDocument, EvaluationCase, EvaluationRecord

MAX_KNOWLEDGE_ITEMS = 20
MAX_DOCUMENT_CHARACTERS = 50_000
MAX_TOTAL_CHARACTERS = 100_000
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class BuilderHTTPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: HttpUrl
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    cleanup_attempts: int = Field(default=3, ge=1, le=3)
    cleanup_backoff_seconds: float = Field(default=0.25, ge=0, le=2)


def _validate_corpus(corpus: list[CorpusDocument]) -> None:
    if not corpus or len(corpus) > MAX_KNOWLEDGE_ITEMS:
        raise AdapterError(f"Builder corpus must contain 1-{MAX_KNOWLEDGE_ITEMS} documents")
    total = sum(len(document.content) for document in corpus)
    if any(len(document.content) > MAX_DOCUMENT_CHARACTERS for document in corpus):
        raise AdapterError("A corpus document exceeds the Builder's 50,000 character limit")
    if total > MAX_TOTAL_CHARACTERS:
        raise AdapterError("Corpus exceeds the Builder's 100,000 character limit")
    if len({document.source_id for document in corpus}) != len(corpus):
        raise AdapterError("Corpus source IDs must be unique")


class BuilderHTTPAdapter:
    def __init__(self, config: BuilderHTTPConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        self.base_url = str(config.base_url).rstrip("/")

    def _request(self, method: str, path: str, *, json: dict | None = None) -> httpx.Response:
        try:
            response = self.client.request(
                method, f"{self.base_url}{path}", json=json, headers={"Accept": "application/json"}
            )
        except httpx.HTTPError as error:
            raise AdapterError(f"Builder HTTP request failed ({type(error).__name__})") from None
        if len(response.content) > self.config.max_response_bytes:
            raise AdapterError("Builder response exceeded configured size limit")
        if not 200 <= response.status_code < 300:
            raise AdapterError(f"Builder returned status {response.status_code}")
        return response

    def _health_mode(self) -> str:
        response = self._request("GET", "/api/health")
        try:
            body = response.json()
        except ValueError:
            raise AdapterError("Builder health endpoint returned invalid JSON") from None
        mode = body.get("mode") if isinstance(body, dict) else None
        if mode not in {"live", "demo"}:
            raise AdapterError("Builder health response did not identify its runtime mode")
        return mode

    def _cleanup(self, session_id: str) -> None:
        last_error: AdapterError | None = None
        for attempt in range(self.config.cleanup_attempts):
            try:
                self._request("DELETE", "/api/knowledge", json={"sessionId": session_id})
                return
            except AdapterError as error:
                last_error = error
                status = None
                if error.args and isinstance(error.args[0], str):
                    suffix = error.args[0].rsplit(" ", 1)[-1]
                    status = int(suffix) if suffix.isdigit() else None
                if (
                    status not in RETRYABLE_STATUS_CODES
                    or attempt + 1 == self.config.cleanup_attempts
                ):
                    break
                delay = min(
                    self.config.cleanup_backoff_seconds * (2**attempt),
                    2.0,
                )
                time.sleep(delay)
        if last_error:
            raise AdapterError(
                "Builder session cleanup failed; the session may expire by TTL"
            ) from None

    def predict(
        self,
        case: EvaluationCase,
        corpus: list[CorpusDocument],
        target_revision: str,
        *,
        require_semantic: bool = True,
    ) -> EvaluationRecord:
        _validate_corpus(corpus)
        mode = self._health_mode()
        if require_semantic and mode != "live":
            raise AdapterError(
                "Semantic track requires a live Builder; health endpoint reports demo mode"
            )
        session_id = str(uuid4())
        primary_error: Exception | None = None
        try:
            for document in corpus:
                source = {
                    "id": document.source_id,
                    "title": document.title,
                    "content": document.content,
                    "type": "text",
                    "metadata": {"sourcePath": document.source_path},
                }
                self._request(
                    "PUT",
                    "/api/knowledge",
                    json={"sessionId": session_id, "source": source},
                )
            response = self._request(
                "POST",
                "/api/chat",
                json={
                    "sessionId": session_id,
                    "message": case.question,
                    "type": "faq",
                    "knowledgeIds": [document.source_id for document in corpus],
                },
            )
            try:
                body = response.json()
            except ValueError:
                raise AdapterError("Builder chat endpoint returned invalid JSON") from None
            if not isinstance(body, dict):
                raise AdapterError("Builder chat response must be a JSON object")
            answer = body.get("reply")
            chunks = body.get("chunks")
            retrieval_mode = body.get("retrievalMode")
            if not isinstance(answer, str):
                raise AdapterError("Builder chat response has no string reply")
            if not isinstance(chunks, list):
                raise AdapterError("Builder chat response has no chunks array")
            if retrieval_mode not in {"semantic", "lexical", "inline", "none"}:
                raise AdapterError("Builder returned an unknown retrieval mode")
            contexts: list[str] = []
            source_ids: list[str] = []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    raise AdapterError("Builder returned a malformed chunk")
                preview = chunk.get("preview")
                knowledge_id = chunk.get("knowledgeId")
                if not isinstance(preview, str) or not isinstance(knowledge_id, str):
                    raise AdapterError("Builder chunk is missing full text or source ID")
                contexts.append(preview)
                source_ids.append(knowledge_id)
            analytics = body.get("analytics")
            metadata = {
                "builder_mode": body.get("mode"),
                "builder_analytics": analytics if isinstance(analytics, dict) else None,
                "builder_usage_cost_status": (
                    "UNVERIFIED; embedding and generation rates/usage incomplete"
                ),
            }
            return EvaluationRecord(
                question_id=case.question_id,
                question=case.question,
                answer=answer,
                retrieved_contexts=contexts,
                retrieved_source_ids=source_ids,
                reference_answer=case.reference_answer,
                reference_evidence=case.reference_evidence,
                expected_source_ids=case.expected_source_ids,
                category=case.category,
                target_revision=target_revision,
                retrieval_mode=retrieval_mode,
                metadata=metadata,
            )
        except Exception as error:
            primary_error = error
            raise
        finally:
            try:
                self._cleanup(session_id)
            except AdapterError:
                if primary_error is None:
                    raise

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "BuilderHTTPAdapter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
