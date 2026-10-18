"""Small dependency-free lexical retrieval over source and location records."""

from __future__ import annotations

import json
import hashlib
import math
import re
from collections import Counter
from pathlib import Path


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "the", "to", "with", "what", "where", "which",
}


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[\w]+", text.casefold()) if token not in _STOPWORDS]


def _documents(snapshot_dir: Path) -> list[dict]:
    path = snapshot_dir / "documents.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"RAG documents not found: {path}")
    documents = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                document = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {path} line {line_number}") from exc
            if not isinstance(document.get("text"), str):
                raise ValueError(f"document on line {line_number} has no text")
            documents.append(document)
    return documents


def _snapshot_manifest(snapshot_dir: Path) -> dict:
    path = snapshot_dir / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"snapshot manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("complete") is not True:
        raise ValueError(f"snapshot is incomplete and cannot ground retrieval: {manifest.get('snapshot_id')}")
    documents_path = snapshot_dir / "documents.jsonl"
    expected = manifest.get("documents_sha256")
    if not isinstance(expected, str):
        raise ValueError("snapshot manifest does not pin documents.jsonl")
    actual = hashlib.sha256(documents_path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError("snapshot documents hash mismatch")
    return manifest


def retrieve(
    query: str,
    snapshot_dir: Path,
    top_k: int = 5,
    dataset_id: str | None = None,
    record_id: str | None = None,
) -> dict:
    """Return cited source/record chunks; generation is deliberately external."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    snapshot_dir = Path(snapshot_dir)
    manifest = _snapshot_manifest(snapshot_dir)
    documents = _documents(snapshot_dir)
    if dataset_id is not None:
        available = {row["dataset_id"] for row in manifest.get("datasets", [])}
        if dataset_id not in available:
            raise ValueError(f"dataset is not part of snapshot: {dataset_id}")
        documents = [document for document in documents if document.get("dataset_id") == dataset_id]
    if record_id is not None:
        if dataset_id is None:
            raise ValueError("record_id retrieval requires a dataset_id")
        documents = [document for document in documents if document.get("record_id") == str(record_id)]
        if not documents:
            raise ValueError(f"source record is not present in snapshot: {dataset_id}:{record_id}")
    query_terms = list(dict.fromkeys(_tokens(query)))
    if not query_terms:
        raise ValueError("query has no searchable terms")

    tokenized = [_tokens(document["text"]) for document in documents]
    document_frequency = Counter(
        term for terms in tokenized for term in set(terms)
    )
    average_length = sum(map(len, tokenized)) / max(1, len(tokenized))
    ranked = []
    for document, terms in zip(documents, tokenized):
        term_counts = Counter(terms)
        length = len(terms)
        score = 0.0
        for term in query_terms:
            frequency = term_counts[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            score += inverse_frequency * (frequency * 2.2) / (
                frequency + 1.2 * (0.25 + 0.75 * length / max(1, average_length))
            )
        if score > 0:
            ranked.append((score, document))
    ranked.sort(key=lambda item: (-item[0], item[1]["doc_id"]))
    results = []
    for rank, (score, document) in enumerate(ranked[:top_k], start=1):
        results.append({"rank": rank, "score": round(score, 6), **document})
    return {
        "query": query,
        "snapshot_id": manifest["snapshot_id"],
        "dataset_filter": dataset_id,
        "record_filter": record_id,
        "retrieval_method": "BM25-style lexical ranking over registered source metadata and retrieved source records",
        "generation": "not_configured",
        "results": results,
        "citations": [
            {
                "rank": row["rank"],
                "doc_id": row["doc_id"],
                "dataset_id": row["dataset_id"],
                "record_id": row.get("record_id"),
                "source_url": row["source_url"],
                "retrieved_at": row.get("retrieved_at"),
                "evidence_state": row.get("evidence_state"),
            }
            for row in results
        ],
        "context": "\n\n".join(
            f"[{row['rank']}] {row['dataset_id']} ({row['source_url']}): {row['text']}"
            for row in results
        ),
    }
