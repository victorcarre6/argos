from __future__ import annotations

import hashlib
import html
import json
import math
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from time import mktime
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests

from feeds.database import connect
from system.settings import (
    MAX_ITEMS,
    load_sources_config,
    utcnow,
)
from system.state import collection_state, state_lock

ProgressCallback = Callable[[str, str, int, int], None]
PIPELINE_RANGES = {
    "fetch": (0, 45),
    "storage": (45, 55),
    "embedding": (55, 75),
    "summary": (75, 95),
    "telegram": (95, 100),
}


def _pipeline_progress(stage: str, label: str, completed: int, total: int) -> None:
    start, end = PIPELINE_RANGES[stage]
    fraction = min(1.0, max(0.0, completed / total)) if total else 0.0
    with state_lock:
        collection_state["progress"].update(
            stage=stage,
            label=label,
            percent=round(start + (end - start) * fraction, 1),
            completed=completed,
            total=total,
        )


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    ignored = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in ignored
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query, doseq=True),
            "",
        )
    )


def _published_at(entry: Any) -> str:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        if parsed := entry.get(key):
            return datetime.fromtimestamp(mktime(parsed), timezone.utc).isoformat()
    return ""


def _is_recent(published_at: str, max_age_days: int) -> bool:
    if not published_at:
        return True
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return published >= cutoff


def _score(
    title: str,
    summary: str,
    taxonomy: dict[str, list[str]],
    priority: int,
    published_at: str,
    collected_at: str,
    max_age_days: int,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    text = f"{title} {summary}".casefold()
    tags = [
        tag
        for tag, aliases in taxonomy.items()
        if any(
            re.search(rf"(?<!\w){re.escape(alias.casefold())}(?!\w)", text)
            for alias in aliases
        )
    ]
    relevance = min(60, 10 + len(tags) * 10)
    priority_points = {1: 25, 2: 12, 3: 0}.get(priority, 0)
    reference = published_at or collected_at
    freshness = 0
    try:
        published = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        age_days = max(0.0, (current - published).total_seconds() / 86_400)
        half_life_days = max_age_days / 2
        freshness = round(15 * math.exp(-math.log(2) * age_days / half_life_days))
    except (AttributeError, ValueError):
        pass
    return min(100, relevance + priority_points + freshness), tags


def fetch_source(
    category: dict[str, Any],
    source: dict[str, Any],
    force: bool = False,
    max_age_days: int | None = None,
    taxonomy: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    name = str(source.get("name", "source"))
    url = str(source.get("url", ""))
    started = time.perf_counter()
    health = {
        "source": name,
        "category": category.get("name", ""),
        "url": url,
        "last_attempt_at": utcnow(),
        "last_success_at": None,
        "latency_ms": 0,
        "http_status": None,
        "last_error": None,
        "last_item_count": 0,
    }
    if source.get("enabled", True) is False and not force:
        return {"articles": [], "health": health}

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Argos/2.0 (+local RSS reader)",
                "Accept": "application/rss+xml, application/atom+xml, text/xml",
            },
        )
        health["http_status"] = response.status_code
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if max_age_days is None or taxonomy is None:
            source_config = load_sources_config()
            if max_age_days is None:
                max_age_days = int(
                    source_config.get("collection", {}).get("max_age_days", 14)
                )
            if taxonomy is None:
                taxonomy = source_config.get("tags", {})
        max_items = int(source.get("max_items", MAX_ITEMS))
        articles = []
        for entry in feed.entries:
            if len(articles) >= max_items:
                break
            title = _clean_text(entry.get("title"))
            raw_url = str(entry.get("link", "")).strip()
            if not title or not raw_url:
                continue
            published_at = _published_at(entry)
            if not _is_recent(published_at, max_age_days):
                continue
            summary = _clean_text(entry.get("summary", entry.get("description", "")))[
                :1200
            ]
            normalized_url = _normalize_url(raw_url)
            now = utcnow()
            score, tags = _score(
                title,
                summary,
                taxonomy,
                int(source.get("priorité", 3)),
                published_at,
                now,
                max_age_days,
            )
            articles.append(
                {
                    "id": hashlib.sha256(normalized_url.encode()).hexdigest(),
                    "title": title[:500],
                    "url": raw_url,
                    "normalized_url": normalized_url,
                    "source": name,
                    "category": str(category["name"]),
                    "summary": summary,
                    "published_at": published_at,
                    "collected_at": now,
                    "first_seen_at": now,
                    "score": score,
                    "tags": tags,
                    "content_fingerprint": hashlib.sha256(
                        f"{title.lower()}|{summary.lower()}".encode()
                    ).hexdigest(),
                    "duplicate_of": None,
                }
            )
        health.update(last_success_at=utcnow(), last_item_count=len(articles))
        return {"articles": articles, "health": health}
    except Exception as exc:
        health["last_error"] = str(exc)[:500]
        return {"articles": [], "health": health}
    finally:
        health["latency_ms"] = int((time.perf_counter() - started) * 1000)


def save_source_health(health: dict[str, Any]) -> None:
    success = health["last_error"] is None
    with connect() as connection:
        connection.execute(
            """INSERT INTO source_health (
                source, category, url, last_attempt_at, last_success_at,
                latency_ms, http_status, last_error, last_item_count,
                total_successes, total_failures
            ) VALUES (
                :source, :category, :url, :last_attempt_at, :last_success_at,
                :latency_ms, :http_status, :last_error, :last_item_count,
                :success, :failure
            ) ON CONFLICT(source) DO UPDATE SET
                category=excluded.category, url=excluded.url,
                last_attempt_at=excluded.last_attempt_at,
                last_success_at=COALESCE(excluded.last_success_at, source_health.last_success_at),
                latency_ms=excluded.latency_ms, http_status=excluded.http_status,
                last_error=excluded.last_error,
                last_item_count=excluded.last_item_count,
                total_successes=source_health.total_successes+excluded.total_successes,
                total_failures=source_health.total_failures+excluded.total_failures
            """,
            {**health, "success": int(success), "failure": int(not success)},
        )


def _similarity(left: dict[str, Any], right: sqlite3.Row) -> float:
    title = SequenceMatcher(
        None, left["title"].lower(), str(right["title"] or "").lower()
    ).ratio()
    summary = SequenceMatcher(
        None, left["summary"].lower()[:600], str(right["summary"] or "").lower()[:600]
    ).ratio()
    return title * 0.72 + summary * 0.28


def _persist_articles(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"stored": 0, "new": 0, "duplicates": 0, "new_items": []}
    new_items = []
    duplicates = 0
    with connect() as connection:
        candidates = connection.execute(
            """SELECT id, title, summary, duplicate_of FROM articles
            WHERE duplicate_of IS NULL
            ORDER BY COALESCE(published_at, collected_at) DESC LIMIT 500"""
        ).fetchall()
        for item in items:
            existed = connection.execute(
                "SELECT 1 FROM articles WHERE id=?", (item["id"],)
            ).fetchone()
            if not existed:
                best = max(
                    (
                        (_similarity(item, row), row)
                        for row in candidates
                        if row["id"] != item["id"]
                    ),
                    default=(0.0, None),
                    key=lambda pair: pair[0],
                )
                if best[1] and best[0] >= 0.90:
                    item["duplicate_of"] = best[1]["id"]
                    duplicates += 1
                else:
                    new_items.append(item)
                    candidates.append(item)
            connection.execute(
                """INSERT INTO articles (
                    id,title,url,normalized_url,source,category,summary,published_at,
                    collected_at,first_seen_at,score,tags,content_fingerprint,duplicate_of
                ) VALUES (
                    :id,:title,:url,:normalized_url,:source,:category,:summary,
                    :published_at,:collected_at,:first_seen_at,:score,:tags,
                    :content_fingerprint,:duplicate_of
                ) ON CONFLICT(id) DO UPDATE SET
                    collected_at=excluded.collected_at, summary=excluded.summary,
                    published_at=excluded.published_at, score=excluded.score,
                    tags=excluded.tags, content_fingerprint=excluded.content_fingerprint,
                    duplicate_of=excluded.duplicate_of""",
                {**item, "tags": ",".join(item["tags"])},
            )
    return {
        "stored": len(items),
        "new": len(new_items),
        "duplicates": duplicates,
        "new_items": new_items,
    }


def _prune_articles(config: dict[str, Any]) -> int:
    days = max(1, int(config.get("storage", {}).get("retention_days", 60)))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as connection:
        result = connection.execute(
            "DELETE FROM articles WHERE COALESCE(published_at,collected_at) < ?",
            (cutoff,),
        )
    return result.rowcount


def _refresh_scores(config: dict[str, Any], now: datetime | None = None) -> int:
    max_age_days = max(1, int(config.get("collection", {}).get("max_age_days", 14)))
    taxonomy = config.get("tags", {})
    sources = {
        source["name"]: {
            "category": category["name"],
            "priority": int(source.get("priorité", 3)),
        }
        for category in config.get("categories", [])
        for source in category.get("sources", [])
    }
    with connect() as connection:
        rows = connection.execute(
            """SELECT id,title,summary,source,category,published_at,collected_at
            FROM articles"""
        ).fetchall()
        updates = []
        for row in rows:
            metadata = sources.get(
                row["source"],
                {"category": row["category"], "priority": 3},
            )
            score, tags = _score(
                row["title"],
                row["summary"] or "",
                taxonomy,
                metadata["priority"],
                row["published_at"] or "",
                row["collected_at"],
                max_age_days,
                now,
            )
            updates.append((score, ",".join(tags), metadata["category"], row["id"]))
        connection.executemany(
            "UPDATE articles SET score=?,tags=?,category=? WHERE id=?", updates
        )
    return len(updates)


def _start_run(trigger: str) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO collection_runs (trigger,started_at,status)
            VALUES (?,?,'running')""",
            (trigger, utcnow()),
        )
        return int(cursor.lastrowid)


def _finish_run(
    run_id: int,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """UPDATE collection_runs SET finished_at=?,status=?,result_json=?,error=?
            WHERE id=?""",
            (
                utcnow(),
                status,
                json.dumps(result, ensure_ascii=False) if result else None,
                error,
                run_id,
            ),
        )


def _refresh_ai_outputs(
    errors: list[str],
    progress: ProgressCallback = _pipeline_progress,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    from rag.indexing import index_status, sync_index

    try:
        index_result = sync_index(progress=progress)
    except Exception as exc:
        errors.append(f"Index RAG: {exc}")
        return index_status(), None, None

    try:
        from rag.summary_agent import generate_summary

        summary_result = generate_summary(progress=progress)
    except Exception as exc:
        errors.append(f"AI Summary: {exc}")
        return index_result, None, None

    try:
        from system.telegram import send_summary_if_pending

        return index_result, summary_result, send_summary_if_pending(progress=progress)
    except Exception as exc:
        errors.append(f"Telegram: {exc}")
        return index_result, summary_result, None


def collect(trigger: str = "manual") -> None:
    run_id = _start_run(trigger)
    with state_lock:
        collection_state.update(
            running=True,
            started_at=utcnow(),
            finished_at=None,
            result=None,
            error=None,
            progress={
                "stage": "fetch",
                "label": "Préparation de la collecte",
                "percent": 0,
                "completed": 0,
                "total": 0,
                "failed": 0,
            },
        )
    try:
        config = load_sources_config()
        max_age_days = max(1, int(config.get("collection", {}).get("max_age_days", 14)))
        taxonomy = config.get("tags", {})
        tasks = [
            (category, source)
            for category in config["categories"]
            for source in category.get("sources", [])
            if source.get("enabled", True)
        ]
        articles = []
        errors = []
        with state_lock:
            collection_state["progress"] = {
                "stage": "fetch",
                "label": "Collecte des flux RSS",
                "percent": 0,
                "completed": 0,
                "total": len(tasks),
                "failed": 0,
            }
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(tasks)))) as executor:
            futures = {
                executor.submit(
                    fetch_source, category, source, False, max_age_days, taxonomy
                ): source.get("name", "source")
                for category, source in tasks
            }
            for future in as_completed(futures):
                result = future.result()
                save_source_health(result["health"])
                articles.extend(result["articles"])
                if result["health"]["last_error"]:
                    errors.append(
                        f"{futures[future]}: {result['health']['last_error']}"
                    )
                with state_lock:
                    progress = collection_state["progress"]
                    progress["completed"] += 1
                    completed = progress["completed"]
                    if result["health"]["last_error"]:
                        progress["failed"] += 1
                _pipeline_progress(
                    "fetch",
                    f"Flux RSS : {futures[future]}",
                    completed,
                    len(tasks),
                )
        _pipeline_progress("storage", "Persistance des articles", 1, 3)
        stored = _persist_articles(articles)
        _pipeline_progress("storage", "Purge de la rétention", 2, 3)
        pruned = _prune_articles(config)
        _pipeline_progress("storage", "Recalcul des scores et tags", 3, 3)
        rescored = _refresh_scores(config)
        index_result, summary_result, telegram_result = _refresh_ai_outputs(errors)
        result = {
            "sources": len(tasks),
            "failed_sources": collection_state["progress"]["failed"],
            "articles": stored["stored"],
            "new": stored["new"],
            "duplicates": stored["duplicates"],
            "pruned": pruned,
            "rescored": rescored,
            "rag_index": index_result,
            "summary": summary_result,
            "telegram": telegram_result,
            "errors": errors,
        }
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), result=result)
        _finish_run(run_id, "completed_with_errors" if errors else "completed", result)
    except Exception as exc:
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), error=str(exc))
        _finish_run(run_id, "failed", error=str(exc))
