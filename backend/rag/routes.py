from __future__ import annotations

from typing import Any
from uuid import uuid4

from flask import Blueprint, jsonify, request

from rag.agent import answer, clear_session
from rag.indexing import index_status

blueprint = Blueprint("rag", __name__)


@blueprint.get("/api/rag/index/status")
def rag_index_status() -> Any:
    return jsonify(index_status())


@blueprint.post("/api/assistant")
def assistant() -> Any:
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return jsonify(error="prompt requis"), 400
    session_id = str(payload.get("session_id") or uuid4()).strip()[:128]
    if not session_id:
        session_id = str(uuid4())
    try:
        return jsonify(answer(prompt, session_id))
    except Exception as exc:
        return jsonify(error=f"Assistant Nyx indisponible : {exc}"), 503


@blueprint.delete("/api/assistant/session/<session_id>")
def delete_session(session_id: str) -> Any:
    clear_session(session_id)
    return jsonify(status="deleted")
