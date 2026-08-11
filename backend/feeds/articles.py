from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from feeds.database import connect
from system.settings import load_sources_config

blueprint = Blueprint("articles", __name__)


@blueprint.get("/api/articles")
def articles() -> Any:
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    category = request.args.get("category")
    search = request.args.get("search", "").strip()
    include_duplicates = request.args.get("duplicates") == "true"
    clauses = [] if include_duplicates else ["duplicate_of IS NULL"]
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
            f"""SELECT * FROM articles{where}
            ORDER BY COALESCE(published_at,collected_at) DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()
    metadata = {
        source.get("name"): {
            "keys": source.get("keys", []),
            "priorité": source.get("priorité", 3),
        }
        for category_config in load_sources_config().get("categories", [])
        for source in category_config.get("sources", [])
    }
    return jsonify(
        total=total,
        articles=[
            {
                **dict(row),
                "tags": [tag for tag in row["tags"].split(",") if tag],
                **metadata.get(row["source"], {"keys": [], "priorité": 3}),
            }
            for row in rows
        ],
    )


@blueprint.get("/api/stats")
def stats() -> Any:
    with connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM articles WHERE duplicate_of IS NULL"
        ).fetchone()[0]
        sources = connection.execute(
            "SELECT COUNT(DISTINCT source) FROM articles"
        ).fetchone()[0]
        latest = connection.execute(
            "SELECT MAX(collected_at) FROM articles"
        ).fetchone()[0]
    return jsonify(total=total, sources=sources, last_collection=latest)
