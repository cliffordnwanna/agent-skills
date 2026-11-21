"""Portable adapters that translate application outputs into EvaluationRecord."""

from rag_eval_kit.adapters.builder import BuilderHTTPAdapter, BuilderHTTPConfig
from rag_eval_kit.adapters.files import read_jsonl, write_jsonl
from rag_eval_kit.adapters.generic_http import GenericHTTPAdapter, GenericHTTPConfig

__all__ = [
    "BuilderHTTPAdapter",
    "BuilderHTTPConfig",
    "GenericHTTPAdapter",
    "GenericHTTPConfig",
    "read_jsonl",
    "write_jsonl",
]
