from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from feeds.database import connect
from system.settings import load_sources_config, utcnow

blueprint = Blueprint("articles", __name__)


def _source_metadata() -> dict[str, dict[str, Any]]:
    return {
        source.get("name"): {
            "keys": source.get("keys", []),
            "priorité": source.get("priorité", 3),
        }
        for category in load_sources_config().get("categories", [])
        for source in category.get("sources", [])
    }


def _save_feedback(connection: Any, article_id: str, candidate: str) -> bool:
    row = connection.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    if row is None:
        return False
    metadata = _source_metadata().get(row["source"], {"keys": [], "priorité": 3})
    snapshot = {
        **dict(row),
        "view": bool(row["view"]),
        "tags": [tag for tag in row["tags"].split(",") if tag],
        **metadata,
    }
    now = utcnow()
    connection.execute(
        """INSERT INTO signal_feedback
        (article_id,candidate,snapshot_json,created_at,updated_at)
        VALUES (?,?,?,?,?) ON CONFLICT(article_id) DO UPDATE SET
        candidate=excluded.candidate,snapshot_json=excluded.snapshot_json,
        updated_at=excluded.updated_at""",
        (article_id, candidate, json.dumps(snapshot, ensure_ascii=False), now, now),
    )
    return True


@blueprint.get("/api/articles")
def articles() -> Any:
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    category = request.args.get("category")
    search = request.args.get("search", "").strip()
    include_duplicates = request.args.get("duplicates") == "true"
    clauses = ["view = 1"]
    if not include_duplicates:
        clauses.append("duplicate_of IS NULL")
    params: list[Any] = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if search:
        clauses.append("(title LIKE ? OR summary LIKE ? OR tags LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM articles{where}", params
        ).fetchone()[0]
        rows = connection.execute(
            f"""SELECT articles.*,
            (SELECT candidate FROM signal_feedback
             WHERE article_id=articles.id) AS candidate
            FROM articles{where}
            ORDER BY COALESCE(published_at,collected_at) DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
    metadata = _source_metadata()
    return jsonify(
        total=total,
        articles=[
            {
                **dict(row),
                "tags": [tag for tag in row["tags"].split(",") if tag],
                "view": bool(row["view"]),
                **metadata.get(row["source"], {"keys": [], "priorité": 3}),
            }
            for row in rows
        ],
    )


@blueprint.get("/api/articles/favorites")
def favorite_articles() -> Any:
    limit = min(max(request.args.get("limit", 30, type=int), 1), 30)
    with connect() as connection:
        rows = connection.execute("""SELECT snapshot_json FROM signal_feedback
            WHERE candidate = 'good'""").fetchall()
    favorites = []
    for row in rows:
        try:
            snapshot = json.loads(row["snapshot_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(snapshot, dict):
            favorites.append(
                {
                    **snapshot,
                    "view": bool(snapshot.get("view", True)),
                    "candidate": "good",
                }
            )
    favorites.sort(
        key=lambda article: str(article.get("collected_at") or ""), reverse=True
    )
    return jsonify(articles=favorites[:limit], total=len(favorites))


@blueprint.patch("/api/articles/<article_id>/view")
def update_article_view(article_id: str) -> Any:
    value = (request.get_json(silent=True) or {}).get("view")
    if not isinstance(value, bool):
        return jsonify(error="view doit être un booléen"), 400
    with connect() as connection:
        result = connection.execute(
            "UPDATE articles SET view = ? WHERE id = ?", (int(value), article_id)
        )
        if result.rowcount and value is False:
            _save_feedback(connection, article_id, "bad")
    if result.rowcount == 0:
        return jsonify(error="Article introuvable"), 404
    return jsonify(status="saved", view=value)


@blueprint.patch("/api/articles/<article_id>/feedback")
def update_article_feedback(article_id: str) -> Any:
    candidate = (request.get_json(silent=True) or {}).get("candidate")
    if candidate not in {"good", "bad"}:
        return jsonify(error="candidate doit valoir good ou bad"), 400
    with connect() as connection:
        saved = _save_feedback(connection, article_id, candidate)
    if not saved:
        return jsonify(error="Article introuvable"), 404
    return jsonify(status="saved", candidate=candidate)


@blueprint.get("/api/stats")
def stats() -> Any:
    config = load_sources_config()
    active_sources = sum(
        source.get("enabled", True) is not False
        for category in config.get("categories", [])
        for source in category.get("sources", [])
    )
    p1_sources = [
        source["name"]
        for category in config.get("categories", [])
        for source in category.get("sources", [])
        if source.get("enabled", True) is not False and source.get("priorité") == 1
    ]
    max_age_days = max(1, int(config.get("collection", {}).get("max_age_days", 14)))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    with connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM articles WHERE duplicate_of IS NULL"
        ).fetchone()[0]
        collected_sources = connection.execute(
            "SELECT COUNT(DISTINCT source) FROM articles"
        ).fetchone()[0]
        latest = connection.execute(
            "SELECT MAX(collected_at) FROM articles"
        ).fetchone()[0]
        placeholders = ",".join("?" for _ in p1_sources)
        priority_one_recent = (
            connection.execute(
                f"""SELECT COUNT(*) FROM articles WHERE duplicate_of IS NULL
                AND view = 1
                AND source IN ({placeholders})
                AND COALESCE(published_at,collected_at) >= ?""",
                (*p1_sources, cutoff),
            ).fetchone()[0]
            if p1_sources
            else 0
        )
        last_run = connection.execute(
            """SELECT finished_at,result_json FROM collection_runs
            WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    last_result = (
        json.loads(last_run["result_json"])
        if last_run and last_run["result_json"]
        else {}
    )
    last_sources = last_result.get("sources")
    last_failed = last_result.get("failed_sources")
    return jsonify(
        total=total,
        sources=active_sources,
        collected_sources=collected_sources,
        new_signals=last_result.get("new"),
        priority_one_recent=priority_one_recent,
        last_collection=last_run["finished_at"] if last_run else latest,
        last_collection_sources=last_sources,
        last_collection_failed_sources=last_failed,
        last_collection_successful_sources=(
            max(0, last_sources - last_failed)
            if isinstance(last_sources, int) and isinstance(last_failed, int)
            else None
        ),
    )
