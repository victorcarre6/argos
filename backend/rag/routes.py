from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from rag.service import answer, assistant_status

blueprint = Blueprint("rag", __name__)


@blueprint.get("/api/assistant/status")
def status() -> Any:
    return jsonify(assistant_status())


@blueprint.post("/api/assistant")
def assistant() -> Any:
    prompt = str((request.get_json(silent=True) or {}).get("prompt", "")).strip()
    if not prompt:
        return jsonify(error="prompt requis"), 400
    try:
        return jsonify(answer(prompt))
    except Exception as exc:
        return jsonify(error=f"Assistant Nyx indisponible : {exc}"), 503
