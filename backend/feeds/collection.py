from __future__ import annotations

import hashlib
import html
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from time import mktime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests

from feeds.database import connect
from system.settings import (
    MAX_ITEMS,
    TELEGRAM_PATH,
    load_sources_config,
    load_yaml,
    utcnow,
)
from system.state import collection_state, state_lock


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


def _score(title: str, summary: str, keywords: list[str]) -> tuple[int, list[str]]:
    text = f"{title} {summary}".lower()
    tags = [word for word in keywords if word.lower() in text]
    return min(100, 25 + len(tags) * 15), tags


def fetch_source(
    category: dict[str, Any], source: dict[str, Any], force: bool = False
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
        keywords = [str(word) for word in category.get("keywords", [])]
        articles = []
        for entry in feed.entries[: int(source.get("max_items", MAX_ITEMS))]:
            title = _clean_text(entry.get("title"))
            raw_url = str(entry.get("link", "")).strip()
            if not title or not raw_url:
                continue
            summary = _clean_text(entry.get("summary", entry.get("description", "")))[
                :1200
            ]
            normalized_url = _normalize_url(raw_url)
            score, tags = _score(title, summary, keywords)
            now = utcnow()
            articles.append(
                {
                    "id": hashlib.sha256(normalized_url.encode()).hexdigest(),
                    "title": title[:500],
                    "url": raw_url,
                    "normalized_url": normalized_url,
                    "source": name,
                    "category": str(category["name"]),
                    "summary": summary,
                    "published_at": _published_at(entry),
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


def _save_health(health: dict[str, Any]) -> None:
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
    days = max(1, int(config.get("storage", {}).get("retention_days", 180)))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as connection:
        result = connection.execute(
            "DELETE FROM articles WHERE COALESCE(published_at,collected_at) < ?",
            (cutoff,),
        )
    return result.rowcount


def _notify_telegram(items: list[dict[str, Any]]) -> int:
    config = load_yaml(TELEGRAM_PATH)
    if not config.get("enabled"):
        return 0
    token = os.environ.get(str(config.get("bot_token_env", "TELEGRAM_BOT_TOKEN")), "")
    chat_id = str(config.get("chat_id", ""))
    if not token or not chat_id:
        return 0
    threshold = int(config.get("score_threshold", 70))
    selected = [item for item in items if item["score"] >= threshold][
        : int(config.get("max_messages", 5))
    ]
    for item in selected:
        text = (
            f"<b>{html.escape(item['title'])}</b>\n"
            f"{html.escape(item['source'])} · score {item['score']}\n{item['url']}"
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        ).raise_for_status()
    return len(selected)


def collect() -> None:
    with state_lock:
        collection_state.update(
            running=True, started_at=utcnow(), finished_at=None, result=None, error=None
        )
    try:
        config = load_sources_config()
        tasks = [
            (category, source)
            for category in config["categories"]
            for source in category.get("sources", [])
            if source.get("enabled", True)
        ]
        articles = []
        errors = []
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(tasks)))) as executor:
            futures = {
                executor.submit(fetch_source, category, source): source.get(
                    "name", "source"
                )
                for category, source in tasks
            }
            for future in as_completed(futures):
                result = future.result()
                _save_health(result["health"])
                articles.extend(result["articles"])
                if result["health"]["last_error"]:
                    errors.append(
                        f"{futures[future]}: {result['health']['last_error']}"
                    )
        stored = _persist_articles(articles)
        result = {
            "sources": len(tasks),
            "articles": stored["stored"],
            "new": stored["new"],
            "duplicates": stored["duplicates"],
            "pruned": _prune_articles(config),
            "alerts": _notify_telegram(stored["new_items"]),
            "errors": errors,
        }
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), result=result)
    except Exception as exc:
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), error=str(exc))


def save_source_health(health: dict[str, Any]) -> None:
    """Persist a manual source-test result."""
    _save_health(health)
