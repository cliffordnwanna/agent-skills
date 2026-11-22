"""Configurable HTTP adapter for systems with a JSON request/response endpoint."""

import os
import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from rag_eval_kit.adapters.base import (
    AdapterError,
    extract_optional_path,
    extract_path,
    response_text,
    string_list,
)
from rag_eval_kit.models import EvaluationCase, EvaluationRecord


class GenericHTTPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: HttpUrl
    endpoint: str = Field(default="/api/chat", min_length=1, max_length=2048)
    question_field: str = Field(default="question", min_length=1, max_length=128)
    question_id_field: str | None = Field(default=None, max_length=128)
    answer_path: str = Field(default="answer", min_length=1, max_length=256)
    contexts_path: str = Field(default="retrieved_contexts", min_length=1, max_length=256)
    source_ids_path: str = Field(default="retrieved_source_ids", min_length=1, max_length=256)
    retrieval_mode_path: str = Field(default="retrieval_mode", min_length=1, max_length=256)
    abstained_path: str | None = Field(default=None, max_length=256)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_retries: int = Field(default=2, ge=0, le=3)
    retry_backoff_seconds: float = Field(default=0.2, ge=0, le=5)
    request: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional JSON body template. ${question} and ${question_id} in any string value "
            "are replaced. If set, it is sent instead of question_field/question_id_field."
        ),
    )

    @model_validator(mode="after")
    def _check_request_template(self) -> "GenericHTTPConfig":
        if self.request is None:
            return self
        found = _placeholders(self.request)
        unknown = sorted(found - TEMPLATE_VALUES)
        if unknown:
            raise ValueError(
                f"Unknown placeholder in request template: ${{{unknown[0]}}} "
                "(use ${question} or ${question_id})"
            )
        if "question" not in found:
            raise ValueError("The request template must contain ${question}")
        return self


TEMPLATE_VALUES = {"question", "question_id"}
_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")


def _placeholders(node: Any) -> set[str]:
    if isinstance(node, str):
        return set(_PLACEHOLDER.findall(node))
    if isinstance(node, dict):
        return set().union(*(_placeholders(v) for v in node.values()), set())
    if isinstance(node, list):
        return set().union(*(_placeholders(v) for v in node), set())
    return set()


def fill_template(node: Any, values: dict[str, str]) -> Any:
    """Replace ${question} and ${question_id} in string values, in one pass.

    Text that comes from a question is never re-scanned, so a question containing
    "${question_id}" is sent as written.
    """
    if isinstance(node, str):
        return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), node)
    if isinstance(node, dict):
        return {key: fill_template(value, values) for key, value in node.items()}
    if isinstance(node, list):
        return [fill_template(value, values) for value in node]
    return node


def build_payload(config: "GenericHTTPConfig", case: EvaluationCase) -> dict[str, Any]:
    if config.request is not None:
        values = {"question": case.question, "question_id": case.question_id}
        return fill_template(config.request, values)
    payload: dict[str, Any] = {config.question_field: case.question}
    if config.question_id_field:
        payload[config.question_id_field] = case.question_id
    return payload


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def resolve_headers(headers: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name, value in headers.items():

        def replace_env(match: re.Match[str]) -> str:
            env_name = match.group(1)
            if env_name not in os.environ:
                raise AdapterError(f"Required header environment variable is missing: {env_name}")
            return os.environ[env_name]

        resolved[name] = re.sub(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}", replace_env, value)
    return resolved


def url_for(config: GenericHTTPConfig) -> str:
    return urljoin(str(config.base_url).rstrip("/") + "/", config.endpoint.lstrip("/"))


class GenericHTTPAdapter:
    def __init__(self, config: GenericHTTPConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=config.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )

    def fetch(self, case: EvaluationCase) -> Any:
        """Send one question and return the parsed JSON response body."""
        payload = build_payload(self.config, case)
        headers = resolve_headers(self.config.headers)
        response = None
        for attempt in range(self.config.max_retries + 1):
            last = attempt == self.config.max_retries
            try:
                response = self.client.post(url_for(self.config), json=payload, headers=headers)
            except httpx.HTTPError as error:
                if last:
                    raise AdapterError(f"HTTP request failed ({type(error).__name__})") from None
            else:
                if response.status_code not in RETRYABLE_STATUS_CODES or last:
                    break
            time.sleep(self.config.retry_backoff_seconds * (2**attempt))
        if len(response.content) > self.config.max_response_bytes:
            raise AdapterError("HTTP response exceeded configured size limit")
        if not 200 <= response.status_code < 300:
            raise AdapterError(f"HTTP target returned status {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise AdapterError("HTTP target returned invalid JSON") from None
        return body

    def predict(self, case: EvaluationCase, target_revision: str) -> EvaluationRecord:
        return self.parse(case, self.fetch(case), target_revision)

    def parse(self, case: EvaluationCase, body: Any, target_revision: str) -> EvaluationRecord:
        """Turn a JSON response into a record using the configured response paths."""
        answer = response_text(extract_path(body, self.config.answer_path), self.config.answer_path)
        contexts = string_list(
            extract_path(body, self.config.contexts_path), self.config.contexts_path
        )
        source_ids = string_list(
            extract_path(body, self.config.source_ids_path), self.config.source_ids_path
        )
        response_mode = extract_optional_path(body, self.config.retrieval_mode_path)
        if response_mode not in {"semantic", "lexical", "inline", "none"}:
            raise AdapterError("Target returned an unknown retrieval mode")
        abstained_value = extract_optional_path(body, self.config.abstained_path)
        if abstained_value is not None and not isinstance(abstained_value, bool):
            raise AdapterError("Configured abstention field must be boolean")
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
            abstained=abstained_value,
            target_revision=target_revision,
            retrieval_mode=response_mode,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "GenericHTTPAdapter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
