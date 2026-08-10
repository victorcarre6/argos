"""API locale de veille IA : RSS, santé, déduplication et clusters Ollama."""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from time import mktime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
import yaml
from flask import Flask, jsonify, request

ROOT = Path(os.environ.get("APP_ROOT", "/app"))
CONFIG_PATH = Path(os.environ.get("SOURCES_CONFIG", ROOT / "config/sources.yml"))
AI_CONFIG_PATH = Path(os.environ.get("AI_CONFIG", ROOT / "config/ai.yaml"))
TELEGRAM_PATH = Path(os.environ.get("TELEGRAM_CONFIG", ROOT / "config/telegram.yaml"))
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "data/monitoring.db"))
MAX_ITEMS = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "20"))
STARTED_AT = datetime.now(timezone.utc)

app = Flask(__name__)
collection_state: dict[str, Any] = {"running": False, "started_at": None, "finished_at": None, "result": None, "error": None}
cluster_state: dict[str, Any] = {"running": False, "started_at": None, "finished_at": None, "result": None, "error": None}
state_lock = threading.Lock()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else (default or {})


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration introuvable : {CONFIG_PATH}")
    data = load_yaml(CONFIG_PATH)
    data.setdefault("categories", [])
    data.setdefault("storage", {"retention_days": 180})
    return data


def ai_config() -> dict[str, Any]:
    config = load_yaml(AI_CONFIG_PATH)
    config.setdefault("embedding", {"url": "http://192.168.1.11:11434", "model": "nomic-embed-text-v2-moe:latest", "batch_size": 16, "threshold": 0.62})
    config.setdefault("assistant", {"url": "http://192.168.1.11:1434", "model": "qwen3.6:27b", "timeout_seconds": 180})
    return config


def db() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, name: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
    if name not in columns:
        conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {definition}")


def init_db() -> None:
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, normalized_url TEXT,
            source TEXT NOT NULL, category TEXT NOT NULL, summary TEXT, published_at TEXT,
            collected_at TEXT NOT NULL, first_seen_at TEXT, score INTEGER NOT NULL, tags TEXT NOT NULL,
            content_fingerprint TEXT, duplicate_of TEXT
        )""")
        for name, definition in (("normalized_url", "TEXT"), ("first_seen_at", "TEXT"), ("content_fingerprint", "TEXT"), ("duplicate_of", "TEXT")):
            ensure_column(conn, name, definition)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(normalized_url)")
        conn.execute("""CREATE TABLE IF NOT EXISTS source_health (
            source TEXT PRIMARY KEY, category TEXT, url TEXT, last_attempt_at TEXT, last_success_at TEXT,
            latency_ms INTEGER, http_status INTEGER, last_error TEXT, last_item_count INTEGER NOT NULL DEFAULT 0,
            total_successes INTEGER NOT NULL DEFAULT 0, total_failures INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS embeddings (
            article_id TEXT PRIMARY KEY, model TEXT NOT NULL, content_hash TEXT NOT NULL,
            vector_json TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, auto_name TEXT NOT NULL, size INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.execute("CREATE TABLE IF NOT EXISTS article_clusters (article_id TEXT PRIMARY KEY, cluster_id TEXT NOT NULL)")


def validate_config(data: Any) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
        return ["categories doit être une liste"]
    errors: list[str] = []
    for ci, category in enumerate(data["categories"]):
        if not isinstance(category, dict) or not str(category.get("name", "")).strip():
            errors.append(f"categories[{ci}].name est requis")
            continue
        if not isinstance(category.get("sources", []), list):
            errors.append(f"categories[{ci}].sources doit être une liste")
            continue
        for si, source in enumerate(category["sources"]):
            url = str(source.get("url", "")) if isinstance(source, dict) else ""
            if not isinstance(source, dict) or not str(source.get("name", "")).strip():
                errors.append(f"categories[{ci}].sources[{si}].name est requis")
            if urlparse(url).scheme not in {"http", "https"} or not urlparse(url).netloc:
                errors.append(f"categories[{ci}].sources[{si}].url doit être une URL HTTP(S)")
    return errors


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))).strip()


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    ignored = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in ignored]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", urlencode(query, doseq=True), ""))


def entry_published(entry: Any) -> str:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        if parsed := entry.get(key):
            return datetime.fromtimestamp(mktime(parsed), timezone.utc).isoformat()
    return ""


def score_article(title: str, summary: str, keywords: list[str]) -> tuple[int, list[str]]:
    text = f"{title} {summary}".lower()
    tags = [word for word in keywords if word.lower() in text]
    return min(100, 25 + len(tags) * 15), tags


def fetch_source(category: dict[str, Any], source: dict[str, Any], force: bool = False) -> dict[str, Any]:
    name, url = str(source.get("name", "source")), str(source.get("url", ""))
    started = time.perf_counter()
    health = {"source": name, "category": category.get("name", ""), "url": url, "last_attempt_at": utcnow(), "last_success_at": None, "latency_ms": 0, "http_status": None, "last_error": None, "last_item_count": 0}
    if source.get("enabled", True) is False and not force:
        return {"articles": [], "health": health}
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Argos/2.0 (+local RSS reader)", "Accept": "application/rss+xml, application/atom+xml, text/xml"})
        health["http_status"] = response.status_code
        response.raise_for_status()
        feed, items = feedparser.parse(response.content), []
        keywords = [str(word) for word in category.get("keywords", [])]
        for entry in feed.entries[: int(source.get("max_items", MAX_ITEMS))]:
            title, raw_url = clean_text(entry.get("title")), str(entry.get("link", "")).strip()
            if not title or not raw_url:
                continue
            summary = clean_text(entry.get("summary", entry.get("description", "")))[:1200]
            normalized = normalize_url(raw_url)
            score, tags = score_article(title, summary, keywords)
            items.append({"id": hashlib.sha256(normalized.encode()).hexdigest(), "title": title[:500], "url": raw_url, "normalized_url": normalized, "source": name, "category": str(category["name"]), "summary": summary, "published_at": entry_published(entry), "collected_at": utcnow(), "first_seen_at": utcnow(), "score": score, "tags": tags, "content_fingerprint": hashlib.sha256(f'{title.lower()}|{summary.lower()}'.encode()).hexdigest(), "duplicate_of": None})
        health.update(last_success_at=utcnow(), last_item_count=len(items))
        return {"articles": items, "health": health}
    except Exception as exc:
        health["last_error"] = str(exc)[:500]
        return {"articles": [], "health": health}
    finally:
        health["latency_ms"] = int((time.perf_counter() - started) * 1000)


def save_health(health: dict[str, Any]) -> None:
    success = health["last_error"] is None
    with db() as conn:
        conn.execute("""INSERT INTO source_health (source, category, url, last_attempt_at, last_success_at, latency_ms, http_status, last_error, last_item_count, total_successes, total_failures)
            VALUES (:source,:category,:url,:last_attempt_at,:last_success_at,:latency_ms,:http_status,:last_error,:last_item_count,:success,:failure)
            ON CONFLICT(source) DO UPDATE SET category=excluded.category,url=excluded.url,last_attempt_at=excluded.last_attempt_at,last_success_at=COALESCE(excluded.last_success_at,source_health.last_success_at),latency_ms=excluded.latency_ms,http_status=excluded.http_status,last_error=excluded.last_error,last_item_count=excluded.last_item_count,total_successes=source_health.total_successes+excluded.total_successes,total_failures=source_health.total_failures+excluded.total_failures""", {**health, "success": int(success), "failure": int(not success)})


def similarity(left: dict[str, Any], right: sqlite3.Row) -> float:
    title = SequenceMatcher(None, left["title"].lower(), str(right["title"] or "").lower()).ratio()
    summary = SequenceMatcher(None, left["summary"].lower()[:600], str(right["summary"] or "").lower()[:600]).ratio()
    return title * 0.72 + summary * 0.28


def persist_articles(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"stored": 0, "new": 0, "duplicates": 0, "new_items": []}
    new_items, duplicates = [], 0
    with db() as conn:
        candidates = conn.execute("SELECT id,title,summary,duplicate_of FROM articles WHERE duplicate_of IS NULL ORDER BY COALESCE(published_at,collected_at) DESC LIMIT 500").fetchall()
        for item in items:
            existed = conn.execute("SELECT 1 FROM articles WHERE id=?", (item["id"],)).fetchone() is not None
            if not existed:
                best = max(((similarity(item, row), row) for row in candidates if row["id"] != item["id"]), default=(0.0, None), key=lambda pair: pair[0])
                if best[1] and best[0] >= 0.90:
                    item["duplicate_of"] = best[1]["id"]
                    duplicates += 1
                else:
                    new_items.append(item)
                    candidates.append({"id": item["id"], "title": item["title"], "summary": item["summary"], "duplicate_of": None})
            conn.execute("""INSERT INTO articles (id,title,url,normalized_url,source,category,summary,published_at,collected_at,first_seen_at,score,tags,content_fingerprint,duplicate_of)
                VALUES (:id,:title,:url,:normalized_url,:source,:category,:summary,:published_at,:collected_at,:first_seen_at,:score,:tags,:content_fingerprint,:duplicate_of)
                ON CONFLICT(id) DO UPDATE SET collected_at=excluded.collected_at,summary=excluded.summary,published_at=excluded.published_at,score=excluded.score,tags=excluded.tags,content_fingerprint=excluded.content_fingerprint,duplicate_of=excluded.duplicate_of""", {**item, "tags": ",".join(item["tags"])})
    return {"stored": len(items), "new": len(new_items), "duplicates": duplicates, "new_items": new_items}


def prune_articles(config: dict[str, Any]) -> int:
    days = max(1, int(config.get("storage", {}).get("retention_days", 180)))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db() as conn:
        result = conn.execute("DELETE FROM articles WHERE COALESCE(published_at,collected_at) < ?", (cutoff,))
    return result.rowcount


def telegram_notify(items: list[dict[str, Any]]) -> int:
    config = load_yaml(TELEGRAM_PATH)
    if not config.get("enabled"):
        return 0
    token = os.environ.get(str(config.get("bot_token_env", "TELEGRAM_BOT_TOKEN")), "")
    chat_id = str(config.get("chat_id", ""))
    if not token or not chat_id:
        return 0
    threshold, limit = int(config.get("score_threshold", 70)), int(config.get("max_messages", 5))
    selected = [item for item in items if item["score"] >= threshold][:limit]
    for item in selected:
        text = f"<b>{html.escape(item['title'])}</b>\n{html.escape(item['source'])} · score {item['score']}\n{item['url']}"
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10).raise_for_status()
    return len(selected)


def collect() -> None:
    with state_lock:
        collection_state.update(running=True, started_at=utcnow(), finished_at=None, result=None, error=None)
    try:
        config = load_config()
        tasks = [(category, source) for category in config["categories"] for source in category.get("sources", []) if source.get("enabled", True)]
        items, errors = [], []
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(tasks)))) as executor:
            futures = {executor.submit(fetch_source, category, source): source.get("name", "source") for category, source in tasks}
            for future in as_completed(futures):
                result = future.result()
                save_health(result["health"])
                items.extend(result["articles"])
                if result["health"]["last_error"]:
                    errors.append(f"{futures[future]}: {result['health']['last_error']}")
        stored = persist_articles(items)
        result = {"sources": len(tasks), "articles": stored["stored"], "new": stored["new"], "duplicates": stored["duplicates"], "pruned": prune_articles(config), "alerts": telegram_notify(stored["new_items"]), "errors": errors}
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), result=result)
    except Exception as exc:
        with state_lock:
            collection_state.update(running=False, finished_at=utcnow(), error=str(exc))


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


def embed_and_cluster() -> None:
    with state_lock:
        cluster_state.update(running=True, started_at=utcnow(), finished_at=None, result=None, error=None)
    try:
        cfg, emb = ai_config(), ai_config()["embedding"]
        model, batch_size = str(emb["model"]), max(1, int(emb.get("batch_size", 16)))
        with db() as conn:
            rows = conn.execute("SELECT id,title,summary,tags,content_fingerprint FROM articles WHERE duplicate_of IS NULL ORDER BY COALESCE(published_at,collected_at) DESC LIMIT 300").fetchall()
            known = {row["article_id"]: row["content_hash"] for row in conn.execute("SELECT article_id,content_hash FROM embeddings WHERE model=?", (model,))}
        pending = [row for row in rows if known.get(row["id"]) != row["content_fingerprint"]]
        for index in range(0, len(pending), batch_size):
            batch = pending[index:index + batch_size]
            response = requests.post(f"{str(emb['url']).rstrip('/')}/api/embed", json={"model": model, "input": [f"{row['title']}\n{row['summary']}"[:2000] for row in batch]}, timeout=120)
            response.raise_for_status()
            vectors = response.json().get("embeddings", [])
            if len(vectors) != len(batch):
                raise ValueError("Réponse d'embedding incomplète")
            with db() as conn:
                conn.executemany("INSERT INTO embeddings (article_id,model,content_hash,vector_json,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(article_id) DO UPDATE SET model=excluded.model,content_hash=excluded.content_hash,vector_json=excluded.vector_json,updated_at=excluded.updated_at", [(row["id"], model, row["content_fingerprint"], json.dumps(vector), utcnow()) for row, vector in zip(batch, vectors)])
        with db() as conn:
            vectors = conn.execute("SELECT a.id,a.title,a.tags,e.vector_json FROM articles a JOIN embeddings e ON e.article_id=a.id WHERE a.duplicate_of IS NULL AND e.model=?", (model,)).fetchall()
            old = {row["article_id"]: row["cluster_id"] for row in conn.execute("SELECT article_id,cluster_id FROM article_clusters")}
        parent = list(range(len(vectors)))
        def find(item: int) -> int:
            while parent[item] != item:
                parent[item] = parent[parent[item]]; item = parent[item]
            return item
        def union(left: int, right: int) -> None:
            left, right = find(left), find(right)
            if left != right: parent[right] = left
        decoded = [json.loads(row["vector_json"]) for row in vectors]
        threshold = float(emb.get("threshold", 0.82))
        for left in range(len(decoded)):
            for right in range(left):
                if cosine(decoded[left], decoded[right]) >= threshold:
                    union(left, right)
        groups: dict[int, list[sqlite3.Row]] = {}
        for index, row in enumerate(vectors): groups.setdefault(find(index), []).append(row)
        refreshed, clustered = 0, 0
        with db() as conn:
            conn.execute("DELETE FROM article_clusters")
            for group in groups.values():
                if len(group) < 2: continue
                prior = [old.get(row["id"]) for row in group if old.get(row["id"])]
                cluster_id = max(set(prior), key=prior.count) if prior else hashlib.sha256("|".join(sorted(row["id"] for row in group)).encode()).hexdigest()[:16]
                existing = conn.execute("SELECT name FROM clusters WHERE id=?", (cluster_id,)).fetchone()
                words = [tag for row in group for tag in str(row["tags"] or "").split(",") if tag]
                auto_name = ", ".join(sorted(set(words), key=words.count, reverse=True)[:3]) or group[0]["title"][:60]
                conn.execute("INSERT INTO clusters (id,name,auto_name,size,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET auto_name=excluded.auto_name,size=excluded.size,updated_at=excluded.updated_at", (cluster_id, existing["name"] if existing else auto_name, auto_name, len(group), utcnow()))
                conn.executemany("INSERT INTO article_clusters (article_id,cluster_id) VALUES (?,?)", [(row["id"], cluster_id) for row in group])
                refreshed += 1; clustered += len(group)
        with state_lock:
            cluster_state.update(running=False, finished_at=utcnow(), result={"embedded": len(pending), "clusters": refreshed, "articles": clustered, "model": model})
    except Exception as exc:
        with state_lock:
            cluster_state.update(running=False, finished_at=utcnow(), error=str(exc))


def rag_retrieve(prompt: str, limit: int = 6) -> list[dict[str, Any]]:
    emb = ai_config()["embedding"]; model = str(emb["model"])
    endpoint = str(emb["url"]).rstrip("/") + "/api/embed"
    response = requests.post(endpoint, json={"model": model, "input": [prompt[:4000]]}, timeout=60)
    response.raise_for_status(); query = response.json().get("embeddings", [[]])[0]
    with db() as conn:
        rows = conn.execute("SELECT a.id,a.title,a.summary,a.url,a.source,a.category,a.published_at,e.vector_json FROM articles a JOIN embeddings e ON e.article_id=a.id WHERE a.duplicate_of IS NULL AND e.model=?", (model,)).fetchall()
    ranked = sorted(({**dict(row), "similarity": cosine(query, json.loads(row["vector_json"]))} for row in rows), key=lambda item: item["similarity"], reverse=True)[:limit]
    return [{key: value for key, value in item.items() if key != "vector_json"} for item in ranked]


def assistant_status() -> dict[str, Any]:
    config = ai_config()["assistant"]
    try:
        response = requests.get(f"{str(config['url']).rstrip('/')}/api/tags", timeout=3)
        return {"available": response.ok, "url": config["url"], "model": config["model"], "error": None if response.ok else response.text[:120]}
    except Exception as exc:
        return {"available": False, "url": config["url"], "model": config["model"], "error": str(exc)}


@app.get("/api/health")
def health() -> Any:
    return jsonify(status="ok", timestamp=utcnow())


@app.get("/api/health/app")
def app_health() -> Any:
    with db() as conn:
        articles_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        duplicates = conn.execute("SELECT COUNT(*) FROM articles WHERE duplicate_of IS NOT NULL").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM source_health WHERE last_error IS NOT NULL").fetchone()[0]
        successful = conn.execute("SELECT COUNT(*) FROM source_health WHERE last_error IS NULL AND last_success_at IS NOT NULL").fetchone()[0]
    return jsonify(status="ok", uptime_seconds=int((datetime.now(timezone.utc)-STARTED_AT).total_seconds()), database_bytes=DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0, articles=articles_count, duplicates=duplicates, sources_healthy=successful, sources_failing=failed, collection=collection_state, clusters=cluster_state, assistant=assistant_status())


@app.get("/api/health/sources")
def sources_health() -> Any:
    with db() as conn:
        rows = conn.execute("SELECT * FROM source_health ORDER BY CASE WHEN last_error IS NULL THEN 0 ELSE 1 END, source").fetchall()
    return jsonify(sources=[dict(row) for row in rows])


@app.post("/api/health/sources/test")
def test_source() -> Any:
    payload = request.get_json(silent=True) or {}
    source, category = payload.get("source"), payload.get("category")
    if not isinstance(source, dict) or not isinstance(category, dict):
        return jsonify(error="source et category sont requis"), 400
    result = fetch_source(category, source, force=True)
    save_health(result["health"])
    return jsonify(health=result["health"]), (200 if not result["health"]["last_error"] else 502)


@app.get("/api/sources")
def sources() -> Any: return jsonify(load_config())


@app.get("/api/sources.yml")
def sources_yaml_file() -> Any:
    return CONFIG_PATH.read_text(encoding="utf-8"), 200, {"Content-Type": "text/yaml; charset=utf-8"}


@app.get("/api/sources/yaml")
def sources_yaml() -> Any:
    return jsonify(content=CONFIG_PATH.read_text(encoding="utf-8"))


@app.put("/api/sources/yaml")
def save_sources_yaml() -> Any:
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    if not isinstance(content, str): return jsonify(error="Contenu YAML manquant"), 400
    try:
        config = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        return jsonify(error=f"YAML invalide : {exc}"), 400
    errors = validate_config(config)
    if errors: return jsonify(error="Configuration invalide", details=errors), 400
    CONFIG_PATH.write_text(content.rstrip() + "\n", encoding="utf-8")
    return jsonify(ok=True, config=config)


@app.put("/api/sources")
def save_sources() -> Any:
    payload = request.get_json(silent=True); errors = validate_config(payload)
    if errors: return jsonify(error="Configuration invalide", details=errors), 400
    temporary = CONFIG_PATH.with_suffix(".tmp"); temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"); temporary.replace(CONFIG_PATH)
    return jsonify(status="saved")


@app.get("/api/articles")
def articles() -> Any:
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    category, search, duplicates = request.args.get("category"), request.args.get("search", "").strip(), request.args.get("duplicates") == "true"
    clauses, params = ([] if duplicates else ["duplicate_of IS NULL"]), []
    if category: clauses.append("category = ?"); params.append(category)
    if search:
        clauses.append("(title LIKE ? OR summary LIKE ? OR tags LIKE ?)"); params.extend([f"%{search}%"] * 3)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM articles{where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM articles{where} ORDER BY COALESCE(published_at,collected_at) DESC LIMIT ?", [*params, limit]).fetchall()
    return jsonify(total=total, articles=[{**dict(row), "tags": [tag for tag in row["tags"].split(",") if tag]} for row in rows])


@app.get("/api/stats")
def stats() -> Any:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles WHERE duplicate_of IS NULL").fetchone()[0]
        sources_count = conn.execute("SELECT COUNT(DISTINCT source) FROM articles").fetchone()[0]
        latest = conn.execute("SELECT MAX(collected_at) FROM articles").fetchone()[0]
    return jsonify(total=total, sources=sources_count, last_collection=latest)


@app.route("/api/collect", methods=["GET", "POST"])
@app.route("/api/refresh", methods=["GET", "POST"])
def collect_endpoint() -> Any:
    with state_lock:
        if request.method == "POST" and not collection_state["running"]:
            collection_state.update(running=True, started_at=utcnow(), finished_at=None, result=None, error=None); threading.Thread(target=collect, daemon=True).start()
        return jsonify(collection_state), (202 if collection_state["running"] else 200)


@app.route("/api/clusters", methods=["GET", "POST"])
def clusters() -> Any:
    if request.method == "POST":
        with state_lock:
            if not cluster_state["running"]:
                cluster_state.update(running=True, started_at=utcnow(), finished_at=None, result=None, error=None); threading.Thread(target=embed_and_cluster, daemon=True).start()
            return jsonify(cluster_state), 202
    with db() as conn:
        rows = conn.execute("SELECT c.*, GROUP_CONCAT(a.title, ' || ') AS titles FROM clusters c LEFT JOIN article_clusters ac ON ac.cluster_id=c.id LEFT JOIN articles a ON a.id=ac.article_id GROUP BY c.id ORDER BY c.size DESC").fetchall()
    return jsonify(clusters=[{**dict(row), "titles": str(row["titles"] or "").split(" || ")[:4]} for row in rows], state=cluster_state)


@app.put("/api/clusters/<cluster_id>")
def rename_cluster(cluster_id: str) -> Any:
    name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
    if not name: return jsonify(error="name est requis"), 400
    with db() as conn: conn.execute("UPDATE clusters SET name=? WHERE id=?", (name[:120], cluster_id))
    return jsonify(status="saved")


@app.get("/api/viz/heatmap")
def heatmap() -> Any:
    mode = request.args.get("mode", "source-category")
    with db() as conn:
        if mode == "day":
            rows = conn.execute("SELECT substr(COALESCE(published_at,collected_at),1,10) AS x, category AS y, COUNT(*) AS value FROM articles WHERE duplicate_of IS NULL GROUP BY x,y ORDER BY x").fetchall()
        else:
            rows = conn.execute("SELECT source AS x, category AS y, COUNT(*) AS value FROM articles WHERE duplicate_of IS NULL GROUP BY x,y ORDER BY y,x").fetchall()
    return jsonify(mode=mode, cells=[dict(row) for row in rows])


@app.get("/api/viz/semantic-map")
def semantic_map() -> Any:
    model = str(ai_config()["embedding"]["model"])
    with db() as conn:
        rows = conn.execute("SELECT a.id,a.title,a.summary,a.url,a.source,a.category,a.score,e.vector_json,ac.cluster_id,c.name AS cluster_name FROM articles a JOIN embeddings e ON e.article_id=a.id LEFT JOIN article_clusters ac ON ac.article_id=a.id LEFT JOIN clusters c ON c.id=ac.cluster_id WHERE a.duplicate_of IS NULL AND e.model=? ORDER BY COALESCE(a.published_at,a.collected_at) DESC LIMIT 300", (model,)).fetchall()
    if not rows: return jsonify(points=[], message="Aucun embedding : lancez le clustering.")
    vectors = [json.loads(row["vector_json"]) for row in rows]; pivot = vectors[0]; distant = max(range(len(vectors)), key=lambda i: 1 - cosine(pivot, vectors[i]))
    raw = [(cosine(vector, pivot), cosine(vector, vectors[distant])) for vector in vectors]
    min_x, max_x = min(p[0] for p in raw), max(p[0] for p in raw); min_y, max_y = min(p[1] for p in raw), max(p[1] for p in raw)
    colors = {item.get("name"): item.get("color", "#6d5dfc") for item in load_config().get("categories", [])}
    points = [{"id": row["id"], "title": row["title"], "summary": row["summary"], "url": row["url"], "source": row["source"], "category": row["category"], "score": row["score"], "cluster_id": row["cluster_id"], "cluster_name": row["cluster_name"], "color": colors.get(row["category"], "#6d5dfc"), "x": (raw[i][0]-min_x)/(max_x-min_x or 1), "y": (raw[i][1]-min_y)/(max_y-min_y or 1)} for i,row in enumerate(rows)]
    return jsonify(points=points, embedded=len(points), clusters=len({p["cluster_id"] for p in points if p["cluster_id"]}))


@app.get("/api/assistant/status")
def assistant_health() -> Any: return jsonify(assistant_status())


@app.post("/api/assistant")
def assistant() -> Any:
    prompt = str((request.get_json(silent=True) or {}).get("prompt", "")).strip()
    if not prompt: return jsonify(error="prompt requis"), 400
    config = ai_config()["assistant"]
    try:
        sources = rag_retrieve(prompt)
        context = "\n\n".join("[{}] {}\nSource: {} · {}\n{}".format(index + 1, item["title"], item["source"], item["url"], item["summary"][:1200]) for index, item in enumerate(sources))
        system = "Tu es Argos, assistant de veille IA. Réponds en français uniquement à partir du contexte fourni. Cite les sources sous la forme [1], [2]. Si le contexte est insuffisant, dis-le clairement.\n\nCONTEXTE:\n" + context
        endpoint = str(config["url"]).rstrip("/") + "/api/chat"
        response = requests.post(endpoint, json={"model": config["model"], "stream": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, timeout=int(config.get("timeout_seconds", 180)))
        response.raise_for_status()
        return jsonify(answer=response.json().get("message", {}).get("content", ""), model=config["model"], sources=sources)
    except Exception as exc:
        return jsonify(error=f"Assistant Nyx indisponible : {exc}"), 503


if __name__ == "__main__":
    init_db(); app.run(host="0.0.0.0", port=8000, debug=False)
