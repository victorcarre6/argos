from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Callable

from feeds.database import connect
from system.settings import (
    DATABASE_PATH,
    SOURCE_KEYS,
    load_ai_config,
    load_sources_config,
    utcnow,
)

COLLECTION_NAME = "argos_articles"
INDEX_VERSION = 2


def rag_config() -> dict[str, Any]:
    return load_ai_config()["rag"]


def metadata_key(key: str) -> str:
    ascii_key = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "_", ascii_key.lower()).strip("_")
    return f"key_{normalized}"


def _ollama_embeddings():
    from langchain_ollama import OllamaEmbeddings

    config = load_ai_config()["embedding"]
    return OllamaEmbeddings(base_url=str(config["url"]), model=str(config["model"]))


def vector_store():
    from langchain_chroma import Chroma

    path = rag_config().get("chroma_path") or str(DATABASE_PATH.parent / "chroma")
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_ollama_embeddings(),
        persist_directory=str(path),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _source_metadata() -> dict[str, dict[str, Any]]:
    return {
        source["name"]: source
        for category in load_sources_config().get("categories", [])
        for source in category.get("sources", [])
    }


def _timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _article_metadata(row: Any, source: dict[str, Any]) -> dict[str, Any]:
    published_at = row["published_at"] or row["collected_at"] or ""
    metadata: dict[str, Any] = {
        "article_id": row["id"],
        "title": row["title"],
        "url": row["url"],
        "source": row["source"],
        "category": row["category"],
        "published_at": published_at,
        "published_timestamp": _timestamp(published_at),
        "score": int(row["score"]),
        "priority": int(source.get("priorité", 3)),
        "content_hash": row["content_fingerprint"] or "",
        "metadata_hash": hashlib.sha256(
            json.dumps(
                {
                    "category": row["category"],
                    "source": row["source"],
                    "keys": sorted(source.get("keys", [])),
                    "priority": source.get("priorité", 3),
                    "score": row["score"],
                    "published_at": published_at,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "index_version": INDEX_VERSION,
    }
    selected_keys = set(source.get("keys", []))
    metadata.update({metadata_key(key): key in selected_keys for key in SOURCE_KEYS})
    return metadata


def split_article(
    text: str, metadata: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    config = rag_config()
    if len(text) < int(config.get("split_min_chars", 900)):
        return [(text, metadata)]

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(config.get("chunk_size", 1200)),
        chunk_overlap=int(config.get("chunk_overlap", 180)),
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    return [
        (chunk, {**metadata, "chunk_index": index})
        for index, chunk in enumerate(chunks)
        if chunk.strip()
    ] or [(text, metadata)]


def index_status() -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """SELECT pending,last_attempt_at,last_success_at,last_error
            FROM rag_index_state WHERE id = 1"""
        ).fetchone()
    return (
        {**dict(row), "pending": bool(row["pending"])}
        if row
        else {
            "pending": False,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
        }
    )


def _record_attempt() -> None:
    with connect() as connection:
        connection.execute(
            """UPDATE rag_index_state SET pending = 1, last_attempt_at = ?,
            last_error = NULL WHERE id = 1""",
            (utcnow(),),
        )


def _record_success() -> None:
    with connect() as connection:
        connection.execute(
            """UPDATE rag_index_state SET pending = 0, last_success_at = ?,
            last_error = NULL WHERE id = 1""",
            (utcnow(),),
        )


def _record_failure(error: Exception) -> None:
    with connect() as connection:
        connection.execute(
            """UPDATE rag_index_state SET pending = 1, last_error = ? WHERE id = 1""",
            (str(error)[:1000],),
        )


def _sync_index(
    progress: Callable[[str, str, int, int], None] | None = None,
) -> dict[str, int]:
    from langchain_core.documents import Document

    config = rag_config()
    with connect() as connection:
        rows = connection.execute(
            """SELECT id,title,url,source,category,summary,published_at,collected_at,
            score,content_fingerprint FROM articles WHERE duplicate_of IS NULL
            ORDER BY COALESCE(published_at,collected_at) DESC LIMIT ?""",
            (int(config.get("index_limit", 2000)),),
        ).fetchall()

    store = vector_store()
    sources = _source_metadata()
    indexed = 0
    unchanged = 0
    metadata_updated = 0
    active_article_ids = {row["id"] for row in rows}

    if progress:
        progress("embedding", "Préparation de l’index Chroma", 0, max(1, len(rows)))
    for position, row in enumerate(rows, start=1):
        if progress:
            progress(
                "embedding",
                f"Indexation : {row['title'][:80]}",
                position - 1,
                len(rows),
            )
        metadata = _article_metadata(row, sources.get(row["source"], {}))
        existing = store.get(where={"article_id": row["id"]}, include=["metadatas"])
        existing_metadata = (existing.get("metadatas") or [{}])[0]
        content_unchanged = (
            existing_metadata.get("content_hash") == metadata["content_hash"]
            and existing_metadata.get("index_version") == INDEX_VERSION
        )
        if content_unchanged:
            if existing_metadata.get("metadata_hash") == metadata["metadata_hash"]:
                unchanged += 1
            else:
                updated_metadata = [
                    {**item, **metadata} for item in existing.get("metadatas", [])
                ]
                store._collection.update(
                    ids=existing["ids"], metadatas=updated_metadata
                )
                metadata_updated += 1
            continue
        if existing.get("ids"):
            store.delete(ids=existing["ids"])

        text = f"{row['title']}\n\n{row['summary'] or ''}".strip()
        chunks = split_article(text, metadata)
        ids = [f"{row['id']}:{index}" for index in range(len(chunks))]
        documents = [
            Document(
                page_content=content,
                metadata={**chunk_metadata, "chunk_id": ids[index]},
            )
            for index, (content, chunk_metadata) in enumerate(chunks)
        ]
        store.add_documents(documents, ids=ids)
        indexed += 1

    if progress:
        progress(
            "embedding",
            "Index Chroma synchronisé",
            max(1, len(rows)),
            max(1, len(rows)),
        )

    all_entries = store.get(include=["metadatas"])
    stale_ids = [
        chunk_id
        for chunk_id, metadata in zip(
            all_entries.get("ids", []), all_entries.get("metadatas", [])
        )
        if metadata.get("article_id") not in active_article_ids
    ]
    if stale_ids:
        store.delete(ids=stale_ids)
    return {
        "indexed": indexed,
        "unchanged": unchanged,
        "metadata_updated": metadata_updated,
        "deleted_chunks": len(stale_ids),
    }


def sync_index(
    progress: Callable[[str, str, int, int], None] | None = None,
) -> dict[str, int]:
    """Synchronize Chroma and keep a persistent retry state in SQLite."""
    _record_attempt()
    try:
        result = _sync_index(progress=progress)
    except Exception as exc:
        _record_failure(exc)
        raise
    _record_success()
    return result
