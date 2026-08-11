from __future__ import annotations

import json
from typing import Any

import requests

from clustering.service import cosine_similarity
from feeds.database import connect
from system.settings import load_ai_config


def retrieve(prompt: str, limit: int = 6) -> list[dict[str, Any]]:
    embedding = load_ai_config()["embedding"]
    model = str(embedding["model"])
    response = requests.post(
        f"{str(embedding['url']).rstrip('/')}/api/embed",
        json={"model": model, "input": [prompt[:4000]]},
        timeout=60,
    )
    response.raise_for_status()
    query = response.json().get("embeddings", [[]])[0]
    with connect() as connection:
        rows = connection.execute(
            """SELECT a.id,a.title,a.summary,a.url,a.source,a.category,
            a.published_at,e.vector_json FROM articles a
            JOIN embeddings e ON e.article_id=a.id
            WHERE a.duplicate_of IS NULL AND e.model=?""",
            (model,),
        ).fetchall()
    ranked = sorted(
        (
            {
                **dict(row),
                "similarity": cosine_similarity(query, json.loads(row["vector_json"])),
            }
            for row in rows
        ),
        key=lambda item: item["similarity"],
        reverse=True,
    )[:limit]
    return [
        {key: value for key, value in item.items() if key != "vector_json"}
        for item in ranked
    ]


def assistant_status() -> dict[str, Any]:
    config = load_ai_config()["assistant"]
    try:
        response = requests.get(f"{str(config['url']).rstrip('/')}/api/tags", timeout=3)
        return {
            "available": response.ok,
            "url": config["url"],
            "model": config["model"],
            "error": None if response.ok else response.text[:120],
        }
    except Exception as exc:
        return {
            "available": False,
            "url": config["url"],
            "model": config["model"],
            "error": str(exc),
        }


def answer(prompt: str) -> dict[str, Any]:
    config = load_ai_config()["assistant"]
    sources = retrieve(prompt)
    context = "\n\n".join(
        "[{}] {}\nSource: {} · {}\n{}".format(
            index + 1,
            item["title"],
            item["source"],
            item["url"],
            item["summary"][:1200],
        )
        for index, item in enumerate(sources)
    )
    system = (
        "Tu es Argos, assistant de veille IA. Réponds en français uniquement à "
        "partir du contexte fourni. Cite les sources sous la forme [1], [2]. "
        "Si le contexte est insuffisant, dis-le clairement.\n\nCONTEXTE:\n" + context
    )
    response = requests.post(
        f"{str(config['url']).rstrip('/')}/api/chat",
        json={
            "model": config["model"],
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=int(config.get("timeout_seconds", 180)),
    )
    response.raise_for_status()
    return {
        "answer": response.json().get("message", {}).get("content", ""),
        "model": config["model"],
        "sources": sources,
    }
