from __future__ import annotations

import threading
from typing import Any

from flask import Blueprint, jsonify, request

from feeds.collection import collect
from system.settings import utcnow
from system.state import collection_state, state_lock

blueprint = Blueprint("fetch", __name__)


@blueprint.route("/api/collect", methods=["GET", "POST"])
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
            )
            threading.Thread(target=collect, daemon=True).start()
        status = 202 if collection_state["running"] else 200
        return jsonify(collection_state), status
