"""Validated, framework-independent case, corpus, and prediction contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RetrievalMode = Literal["semantic", "lexical", "inline", "none"]
QuestionCategory = Literal[
    "direct", "paraphrased", "multi_document", "difficult_retrieval", "unanswerable"
]


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    question: str = Field(min_length=1, max_length=4000)
    reference_answer: str = Field(min_length=1, max_length=8000)
    reference_evidence: list[str] = Field(default_factory=list, max_length=20)
    expected_source_ids: list[str] = Field(default_factory=list, max_length=20)
    category: QuestionCategory
    unanswerable: bool = False


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(default="", max_length=20000)
    retrieved_contexts: list[str] = Field(default_factory=list, max_length=20)
    retrieved_source_ids: list[str] = Field(default_factory=list, max_length=20)
    reference_answer: str | None = Field(default=None, max_length=8000)
    reference_evidence: list[str] = Field(default_factory=list, max_length=20)
    target_revision: str = Field(min_length=1, max_length=200)
    retrieval_mode: RetrievalMode
    expected_source_ids: list[str] = Field(default_factory=list, max_length=20)
    category: QuestionCategory | None = None
    abstained: bool | None = None
    latency_ms: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        description="Client-side wall-clock time (monotonic clock, retries included)",
    )
    attempts: int | None = Field(default=None, ge=1, description="HTTP attempts used")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    app_latency_ms: float | None = Field(
        default=None, ge=0, allow_inf_nan=False, description="Time the app itself reported"
    )
    repeat: int = Field(default=1, ge=1)
    run_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50000)
    source_url: str = Field(min_length=1, max_length=2048)
    source_path: str = Field(min_length=1, max_length=512)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CorpusManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    source_path: str = Field(min_length=1, max_length=512)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    source_repository: str = Field(min_length=1, max_length=500)
    source_revision: str = Field(min_length=40, max_length=40)
    license: str = Field(min_length=1, max_length=50)
    license_url: str = Field(min_length=1, max_length=2048)
    documents: list[CorpusManifestDocument] = Field(min_length=1, max_length=20)
    transformations: list[str] = Field(min_length=1)
