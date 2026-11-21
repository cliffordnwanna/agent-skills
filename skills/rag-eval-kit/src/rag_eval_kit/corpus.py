"""Load a provenance-pinned text corpus and verify all local content hashes."""

import hashlib
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from rag_eval_kit.models import CorpusDocument, CorpusManifest


class CorpusError(ValueError):
    pass


def load_corpus(directory: Path) -> tuple[CorpusManifest, list[CorpusDocument], str]:
    manifest_path = directory / "provenance.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = CorpusManifest.model_validate_json(manifest_bytes)
    except OSError as error:
        raise CorpusError(f"Cannot read corpus provenance: {type(error).__name__}") from None
    except ValidationError:
        raise CorpusError("Corpus provenance has an invalid schema") from None

    root = directory.resolve()
    loaded: list[CorpusDocument] = []
    seen: set[str] = set()
    total_characters = 0
    for item in manifest.documents:
        if item.source_id in seen:
            raise CorpusError(f"Duplicate corpus source ID: {item.source_id}")
        seen.add(item.source_id)
        relative = PurePosixPath(item.source_path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in item.source_path:
            raise CorpusError("Corpus paths must be relative POSIX paths without traversal")
        path = (directory / Path(*relative.parts)).resolve()
        if not path.is_relative_to(root):
            raise CorpusError("Corpus path resolves outside the corpus directory")
        try:
            content_bytes = path.read_bytes()
            content = content_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise CorpusError(f"Cannot read corpus document: {type(error).__name__}") from None
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        if content_hash != item.content_sha256:
            raise CorpusError(f"Corpus content hash mismatch: {item.source_id}")
        if len(content) > 50_000:
            raise CorpusError(f"Corpus document exceeds 50,000 characters: {item.source_id}")
        total_characters += len(content)
        loaded.append(
            CorpusDocument(
                **item.model_dump(exclude={"content_sha256"}),
                content=content,
                content_sha256=content_hash,
            )
        )
    if len(loaded) > 20 or total_characters > 100_000:
        raise CorpusError("Corpus exceeds the Builder's item or total-character limit")
    corpus_hash = hashlib.sha256(manifest_bytes).hexdigest()
    return manifest, loaded, corpus_hash
