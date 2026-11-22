"""Deterministic local RAG server used by `ragkit smoke` and adapter tests (no network, no AI)."""

import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rag_eval_kit.models import CorpusDocument, EvaluationCase

DEMO_DOCS = {
    "alpha": "The alpha service listens on port 8080 and logs to standard output.",
    "beta": "The beta worker retries failed jobs three times before giving up.",
    "gamma": "The gamma cache expires entries after sixty seconds.",
}
DEMO_CASES = [
    ("demo-01", "Which port does the alpha service use?", "Port 8080.", "alpha"),
    ("demo-02", "How many times does the beta worker retry a failed job?", "Three times.", "beta"),
    ("demo-03", "When do gamma cache entries expire?", "After sixty seconds.", "gamma"),
]


def demo_corpus() -> list[CorpusDocument]:
    docs = []
    for source_id, text in DEMO_DOCS.items():
        digest = hashlib.sha256(text.encode()).hexdigest()
        docs.append(
            CorpusDocument(
                source_id=source_id,
                title=source_id.title(),
                content=text,
                source_url=f"https://example.invalid/{source_id}",
                source_path=f"{source_id}.txt",
                source_sha256=digest,
                content_sha256=digest,
            )
        )
    return docs


def demo_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            question_id=qid,
            question=q,
            reference_answer=a,
            reference_evidence=[DEMO_DOCS[src]],
            expected_source_ids=[src],
            category="direct",
        )
        for qid, q, a, src in DEMO_CASES
    ]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def make_server(
    docs: dict[str, str] | None = None, *, fail_first: int = 0, mode: str = "lexical"
) -> ThreadingHTTPServer:
    """Create (not start) a server on a free port. `fail_first` returns 503 that many times."""
    corpus = docs or DEMO_DOCS
    state = {"failures_left": fail_first}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            if self.path != "/api/chat":
                return self._send(404, {"error": "not found"})
            with lock:
                if state["failures_left"] > 0:
                    state["failures_left"] -= 1
                    return self._send(503, {"error": "temporarily unavailable"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                question = json.loads(self.rfile.read(length))["question"]
            except (ValueError, KeyError, TypeError):
                return self._send(400, {"error": "question required"})
            qwords = _words(question)
            scored = sorted(
                ((len(qwords & _words(text)), sid, text) for sid, text in corpus.items()),
                reverse=True,
            )
            hits = [(sid, text) for score, sid, text in scored[:1] if score > 1]
            answer = hits[0][1] if hits else "I do not have that information."
            self._send(
                200,
                {
                    "answer": answer,
                    "retrieved_contexts": [t for _, t in hits],
                    "retrieved_source_ids": [s for s, _ in hits],
                    "retrieval_mode": mode,
                },
            )

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def serve_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
