from __future__ import annotations

import json
import threading
from typing import Any

from flask import Blueprint, jsonify, request

from clustering.service import cosine_similarity, embed_and_cluster
from feeds.database import connect
from system.settings import load_ai_config, load_sources_config, utcnow
from system.state import cluster_state, state_lock

blueprint = Blueprint("clustering", __name__)


@blueprint.route("/api/clusters", methods=["GET", "POST"])
def clusters() -> Any:
    if request.method == "POST":
        with state_lock:
            if not cluster_state["running"]:
                cluster_state.update(
                    running=True,
                    started_at=utcnow(),
                    finished_at=None,
                    result=None,
                    error=None,
                )
                threading.Thread(target=embed_and_cluster, daemon=True).start()
            return jsonify(cluster_state), 202
    with connect() as connection:
        rows = connection.execute(
            """SELECT c.*, GROUP_CONCAT(a.title, ' || ') AS titles FROM clusters c
            LEFT JOIN article_clusters ac ON ac.cluster_id=c.id
            LEFT JOIN articles a ON a.id=ac.article_id
            GROUP BY c.id ORDER BY c.size DESC"""
        ).fetchall()
    return jsonify(
        clusters=[
            {**dict(row), "titles": str(row["titles"] or "").split(" || ")[:4]}
            for row in rows
        ],
        state=cluster_state,
    )


@blueprint.put("/api/clusters/<cluster_id>")
def rename_cluster(cluster_id: str) -> Any:
    name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
    if not name:
        return jsonify(error="name est requis"), 400
    with connect() as connection:
        connection.execute(
            "UPDATE clusters SET name=? WHERE id=?", (name[:120], cluster_id)
        )
    return jsonify(status="saved")


@blueprint.get("/api/viz/heatmap")
def heatmap() -> Any:
    mode = request.args.get("mode", "source-category")
    with connect() as connection:
        if mode == "day":
            rows = connection.execute(
                """SELECT substr(COALESCE(published_at,collected_at),1,10) AS x,
                category AS y, COUNT(*) AS value FROM articles
                WHERE duplicate_of IS NULL GROUP BY x,y ORDER BY x"""
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT source AS x, category AS y, COUNT(*) AS value
                FROM articles WHERE duplicate_of IS NULL
                GROUP BY x,y ORDER BY y,x"""
            ).fetchall()
    return jsonify(mode=mode, cells=[dict(row) for row in rows])


@blueprint.get("/api/viz/semantic-map")
def semantic_map() -> Any:
    model = str(load_ai_config()["embedding"]["model"])
    with connect() as connection:
        rows = connection.execute(
            """SELECT a.id,a.title,a.summary,a.url,a.source,a.category,a.score,
            e.vector_json,ac.cluster_id,c.name AS cluster_name FROM articles a
            JOIN embeddings e ON e.article_id=a.id
            LEFT JOIN article_clusters ac ON ac.article_id=a.id
            LEFT JOIN clusters c ON c.id=ac.cluster_id
            WHERE a.duplicate_of IS NULL AND e.model=?
            ORDER BY COALESCE(a.published_at,a.collected_at) DESC LIMIT 300""",
            (model,),
        ).fetchall()
    if not rows:
        return jsonify(points=[], message="Aucun embedding : lancez le clustering.")
    vectors = [json.loads(row["vector_json"]) for row in rows]
    pivot = vectors[0]
    distant = max(
        range(len(vectors)),
        key=lambda index: 1 - cosine_similarity(pivot, vectors[index]),
    )
    raw = [
        (
            cosine_similarity(vector, pivot),
            cosine_similarity(vector, vectors[distant]),
        )
        for vector in vectors
    ]
    min_x, max_x = min(point[0] for point in raw), max(point[0] for point in raw)
    min_y, max_y = min(point[1] for point in raw), max(point[1] for point in raw)
    colors = {
        item.get("name"): item.get("color", "#6d5dfc")
        for item in load_sources_config().get("categories", [])
    }
    points = [
        {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "url": row["url"],
            "source": row["source"],
            "category": row["category"],
            "score": row["score"],
            "cluster_id": row["cluster_id"],
            "cluster_name": row["cluster_name"],
            "color": colors.get(row["category"], "#6d5dfc"),
            "x": (raw[index][0] - min_x) / (max_x - min_x or 1),
            "y": (raw[index][1] - min_y) / (max_y - min_y or 1),
        }
        for index, row in enumerate(rows)
    ]
    return jsonify(
        points=points,
        embedded=len(points),
        clusters=len({point["cluster_id"] for point in points if point["cluster_id"]}),
    )
