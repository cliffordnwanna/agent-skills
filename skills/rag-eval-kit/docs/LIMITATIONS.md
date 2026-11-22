# Limitations

- **Text RAG only.** No image, audio or agent-action evaluation.
- **No hosted service.** It is a local CLI installed from GitHub.
- **Benchmark not yet approved.** The 60 FastAPI candidates are hand-authored and await human review. No baseline or before/after result is published yet; none should be quoted until a frozen run exists.
- **Cost is local accounting.** The budget guard reserves cost per call from configured prices and reported token usage. It is not a provider billing cap, and it does not include the target app's own generation or embedding costs.
- **Retrieval depends on the target.** Context and source-ID metrics need the application to return what it retrieved. Applications that do not expose this can only be scored on answers.
- **Builder adapter assumes the baseline Builder protocol** (`/api/health`, `/api/knowledge`, `/api/chat`) and its limits (20 documents, 50,000 characters each, 100,000 total).
- **Judge compatibility is checked per model.** The only verified judge so far is `gpt-4.1-mini` on three fixture examples.
- **Small samples.** See METHODOLOGY.md.
