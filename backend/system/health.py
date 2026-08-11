from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from feeds.collection import fetch_source, save_source_health
from feeds.database import connect
from rag.service import assistant_status
from system.settings import DATABASE_PATH, STARTED_AT, utcnow
from system.state import cluster_state, collection_state

blueprint = Blueprint("health", __name__)


@blueprint.get("/api/health")
def health() -> Any:
    return jsonify(status="ok", timestamp=utcnow())


@blueprint.get("/api/health/app")
def app_health() -> Any:
    with connect() as connection:
        articles = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        duplicates = connection.execute(
            "SELECT COUNT(*) FROM articles WHERE duplicate_of IS NOT NULL"
        ).fetchone()[0]
        failing = connection.execute(
            "SELECT COUNT(*) FROM source_health WHERE last_error IS NOT NULL"
        ).fetchone()[0]
        healthy = connection.execute("""SELECT COUNT(*) FROM source_health
            WHERE last_error IS NULL AND last_success_at IS NOT NULL""").fetchone()[0]
    return jsonify(
        status="ok",
        uptime_seconds=int((datetime.now(timezone.utc) - STARTED_AT).total_seconds()),
        database_bytes=DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0,
        articles=articles,
        duplicates=duplicates,
        sources_healthy=healthy,
        sources_failing=failing,
        collection=collection_state,
        clusters=cluster_state,
        assistant=assistant_status(),
    )


@blueprint.get("/api/health/sources")
def sources_health() -> Any:
    with connect() as connection:
        rows = connection.execute(
            """SELECT * FROM source_health
            ORDER BY CASE WHEN last_error IS NULL THEN 0 ELSE 1 END, source"""
        ).fetchall()
    return jsonify(sources=[dict(row) for row in rows])


@blueprint.post("/api/health/sources/test")
def test_source() -> Any:
    payload = request.get_json(silent=True) or {}
    source = payload.get("source")
    category = payload.get("category")
    if not isinstance(source, dict) or not isinstance(category, dict):
        return jsonify(error="source et category sont requis"), 400
    result = fetch_source(category, source, force=True)
    save_source_health(result["health"])
    status = 200 if not result["health"]["last_error"] else 502
    return jsonify(health=result["health"]), status
