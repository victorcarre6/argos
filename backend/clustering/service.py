from __future__ import annotations

import hashlib
import json
import math
import sqlite3

import requests

from feeds.database import connect
from system.settings import load_ai_config, utcnow
from system.state import cluster_state, state_lock


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


def _embed_pending_articles(config: dict[str, object]) -> tuple[str, int]:
    model = str(config["model"])
    batch_size = max(1, int(config.get("batch_size", 16)))
    with connect() as connection:
        articles = connection.execute(
            """SELECT id, title, summary, tags, content_fingerprint FROM articles
            WHERE duplicate_of IS NULL
            ORDER BY COALESCE(published_at,collected_at) DESC LIMIT 300"""
        ).fetchall()
        known = {
            row["article_id"]: row["content_hash"]
            for row in connection.execute(
                "SELECT article_id, content_hash FROM embeddings WHERE model=?",
                (model,),
            )
        }
    pending = [
        row for row in articles if known.get(row["id"]) != row["content_fingerprint"]
    ]
    for index in range(0, len(pending), batch_size):
        batch = pending[index : index + batch_size]
        response = requests.post(
            f"{str(config['url']).rstrip('/')}/api/embed",
            json={
                "model": model,
                "input": [f"{row['title']}\n{row['summary']}"[:2000] for row in batch],
            },
            timeout=120,
        )
        response.raise_for_status()
        vectors = response.json().get("embeddings", [])
        if len(vectors) != len(batch):
            raise ValueError("Réponse d'embedding incomplète")
        with connect() as connection:
            connection.executemany(
                """INSERT INTO embeddings (
                    article_id, model, content_hash, vector_json, updated_at
                ) VALUES (?,?,?,?,?) ON CONFLICT(article_id) DO UPDATE SET
                    model=excluded.model, content_hash=excluded.content_hash,
                    vector_json=excluded.vector_json, updated_at=excluded.updated_at""",
                [
                    (
                        row["id"],
                        model,
                        row["content_fingerprint"],
                        json.dumps(vector),
                        utcnow(),
                    )
                    for row, vector in zip(batch, vectors)
                ],
            )
    return model, len(pending)


def _semantic_groups(
    vectors: list[sqlite3.Row], threshold: float
) -> list[list[sqlite3.Row]]:
    parent = list(range(len(vectors)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    decoded = [json.loads(row["vector_json"]) for row in vectors]
    for left in range(len(decoded)):
        for right in range(left):
            if cosine_similarity(decoded[left], decoded[right]) >= threshold:
                union(left, right)

    groups: dict[int, list[sqlite3.Row]] = {}
    for index, row in enumerate(vectors):
        groups.setdefault(find(index), []).append(row)
    return list(groups.values())


def _store_clusters(model: str, threshold: float) -> tuple[int, int]:
    with connect() as connection:
        vectors = connection.execute(
            """SELECT a.id, a.title, a.tags, e.vector_json FROM articles a
            JOIN embeddings e ON e.article_id=a.id
            WHERE a.duplicate_of IS NULL AND e.model=?""",
            (model,),
        ).fetchall()
        previous = {
            row["article_id"]: row["cluster_id"]
            for row in connection.execute(
                "SELECT article_id, cluster_id FROM article_clusters"
            )
        }

    refreshed = 0
    clustered = 0
    with connect() as connection:
        connection.execute("DELETE FROM article_clusters")
        for group in _semantic_groups(vectors, threshold):
            if len(group) < 2:
                continue
            prior_ids = [
                previous.get(row["id"]) for row in group if previous.get(row["id"])
            ]
            cluster_id = (
                max(set(prior_ids), key=prior_ids.count)
                if prior_ids
                else hashlib.sha256(
                    "|".join(sorted(row["id"] for row in group)).encode()
                ).hexdigest()[:16]
            )
            existing = connection.execute(
                "SELECT name FROM clusters WHERE id=?", (cluster_id,)
            ).fetchone()
            words = [
                tag for row in group for tag in str(row["tags"] or "").split(",") if tag
            ]
            auto_name = (
                ", ".join(sorted(set(words), key=words.count, reverse=True)[:3])
                or group[0]["title"][:60]
            )
            connection.execute(
                """INSERT INTO clusters (id,name,auto_name,size,updated_at)
                VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    auto_name=excluded.auto_name, size=excluded.size,
                    updated_at=excluded.updated_at""",
                (
                    cluster_id,
                    existing["name"] if existing else auto_name,
                    auto_name,
                    len(group),
                    utcnow(),
                ),
            )
            connection.executemany(
                "INSERT INTO article_clusters (article_id,cluster_id) VALUES (?,?)",
                [(row["id"], cluster_id) for row in group],
            )
            refreshed += 1
            clustered += len(group)
    return refreshed, clustered


def embed_and_cluster() -> None:
    with state_lock:
        cluster_state.update(
            running=True, started_at=utcnow(), finished_at=None, result=None, error=None
        )
    try:
        config = load_ai_config()["embedding"]
        model, embedded = _embed_pending_articles(config)
        clusters, articles = _store_clusters(
            model, float(config.get("threshold", 0.82))
        )
        with state_lock:
            cluster_state.update(
                running=False,
                finished_at=utcnow(),
                result={
                    "embedded": embedded,
                    "clusters": clusters,
                    "articles": articles,
                    "model": model,
                },
            )
    except Exception as exc:
        with state_lock:
            cluster_state.update(running=False, finished_at=utcnow(), error=str(exc))
