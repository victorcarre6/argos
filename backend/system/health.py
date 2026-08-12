from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from feeds.collection import fetch_source, save_source_health
from feeds.database import connect
from rag.agent import assistant_status
from rag.indexing import index_status
from system.reports import latest_report_path, report_updated_at
from system.settings import (
    DATABASE_PATH,
    SUMMARY_PATH,
    STARTED_AT,
    TIMER_PATH,
    load_sources_config,
    utcnow,
)
from system.telegram import telegram_status

blueprint = Blueprint("health", __name__)


def _storage_bytes() -> int:
    total = 0
    for path in DATABASE_PATH.parent.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def automation_status() -> dict[str, Any]:
    if not TIMER_PATH.exists():
        return {"configured": False, "calendar": None, "times": [], "persistent": False}
    values = {}
    for line in TIMER_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith(("#", ";")):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    calendar = values.get("OnCalendar")
    match = re.fullmatch(r"\*-\*-\*\s+([0-9,]+):(\d{2}):(\d{2})", calendar or "")
    times = (
        [f"{int(hour):02d}:{match.group(2)}" for hour in match.group(1).split(",")]
        if match
        else []
    )
    return {
        "configured": bool(calendar),
        "calendar": calendar,
        "times": times,
        "persistent": values.get("Persistent", "false").casefold() == "true",
    }


@blueprint.get("/api/health")
def health() -> Any:
    return jsonify(status="ok", timestamp=utcnow())


@blueprint.get("/api/summary")
def summary() -> Any:
    report = latest_report_path(SUMMARY_PATH)
    if report is None:
        response = jsonify(content="", updated_at=None, filename=None)
    else:
        response = jsonify(
            content=report.read_text(encoding="utf-8"),
            updated_at=report_updated_at(report),
            filename=report.name,
        )
    response.headers["Cache-Control"] = "no-store"
    return response


@blueprint.get("/api/summary/download")
def download_summary() -> Any:
    report = latest_report_path(SUMMARY_PATH)
    if report is None:
        return jsonify(error="Aucun rapport disponible"), 404
    return send_file(
        report,
        as_attachment=True,
        download_name=report.name,
        mimetype="text/markdown",
    )


@blueprint.get("/api/health/app")
def app_health() -> Any:
    config = load_sources_config()
    p1_sources = [
        source["name"]
        for category in config.get("categories", [])
        for source in category.get("sources", [])
        if source.get("priorité") == 1
    ]
    with connect() as connection:
        signals_total = connection.execute(
            "SELECT COUNT(*) FROM articles WHERE duplicate_of IS NULL"
        ).fetchone()[0]
        placeholders = ",".join("?" for _ in p1_sources)
        signals_p1 = (
            connection.execute(
                f"""SELECT COUNT(*) FROM articles
                WHERE duplicate_of IS NULL AND source IN ({placeholders})""",
                p1_sources,
            ).fetchone()[0]
            if p1_sources
            else 0
        )
        failing = connection.execute(
            "SELECT COUNT(*) FROM source_health WHERE last_error IS NOT NULL"
        ).fetchone()[0]
        healthy = connection.execute("""SELECT COUNT(*) FROM source_health
            WHERE last_error IS NULL AND last_success_at IS NOT NULL""").fetchone()[0]
    return jsonify(
        status="ok",
        uptime_seconds=int((datetime.now(timezone.utc) - STARTED_AT).total_seconds()),
        storage_bytes=_storage_bytes(),
        signals_total=signals_total,
        signals_p1=signals_p1,
        sources_healthy=healthy,
        sources_failing=failing,
        assistant=assistant_status(),
        telegram=telegram_status(),
        automation=automation_status(),
        rag_index=index_status(),
    )


@blueprint.get("/api/health/sources")
def sources_health() -> Any:
    configured = {
        source["name"]: {"category": category["name"], "url": source["url"]}
        for category in load_sources_config().get("categories", [])
        for source in category.get("sources", [])
        if source.get("enabled", True) is not False
    }
    with connect() as connection:
        rows = connection.execute("SELECT * FROM source_health").fetchall()
    sources = [
        {**dict(row), **configured[row["source"]]}
        for row in rows
        if row["source"] in configured
    ]
    sources.sort(key=lambda source: (not bool(source["last_error"]), source["source"]))
    return jsonify(sources=sources)


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
