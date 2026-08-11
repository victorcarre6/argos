from __future__ import annotations

import json
import threading
from typing import Any

from flask import Blueprint, jsonify, request

from feeds.collection import collect
from system.settings import utcnow
from system.state import collection_state, state_lock

blueprint = Blueprint("fetch", __name__)


@blueprint.route("/api/refresh", methods=["GET", "POST"])
def collection() -> Any:
    with state_lock:
        if request.method == "POST" and not collection_state["running"]:
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
            trigger = request.args.get("trigger", "manual")
            if trigger not in {"manual", "systemd"}:
                trigger = "manual"
            threading.Thread(target=collect, args=(trigger,), daemon=True).start()
        status = 202 if collection_state["running"] else 200
        return jsonify(collection_state), status


@blueprint.get("/api/collection/runs")
def collection_runs() -> Any:
    from feeds.database import connect

    limit = max(1, min(request.args.get("limit", default=10, type=int), 50))
    with connect() as connection:
        rows = connection.execute(
            """SELECT id,trigger,started_at,finished_at,status,result_json,error
            FROM collection_runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return jsonify(
        runs=[
            {
                **dict(row),
                "result": (
                    json.loads(row["result_json"]) if row["result_json"] else None
                ),
            }
            for row in rows
        ]
    )
