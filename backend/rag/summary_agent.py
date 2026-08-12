from __future__ import annotations

import threading
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypedDict

from feeds.database import connect
from rag.models import chat_model
from rag.prompts import load_prompt
from rag.retrieve import retrieve
from system.reports import (
    REPORT_TIMEZONE,
    latest_report_path,
    report_path,
    report_updated_at,
)
from system.settings import SUMMARY_PATH, load_ai_config, load_sources_config


class SummaryState(TypedDict, total=False):
    signals: list[dict[str, Any]]
    drafts: list[dict[str, str]]
    document: str
    generated_at: str


_graph: Any | None = None
_graph_lock = threading.Lock()
_progress_callback: ContextVar[Callable[[str, str, int, int], None] | None] = (
    ContextVar("summary_progress", default=None)
)


def _progress(label: str, completed: int, total: int) -> None:
    callback = _progress_callback.get()
    if callback:
        callback("summary", label, completed, total)


def _new_p1_signals() -> list[dict[str, Any]]:
    config = load_sources_config()
    top_n = max(1, int(load_ai_config()["summary"]["top_n"]))
    p1_sources = [
        source["name"]
        for category in config.get("categories", [])
        for source in category.get("sources", [])
        if source.get("enabled", True) is not False and source.get("priorité") == 1
    ]
    if not p1_sources:
        return []
    latest_report = latest_report_path(SUMMARY_PATH)
    if latest_report:
        cutoff = report_updated_at(latest_report)
    else:
        max_age_days = max(1, int(config.get("collection", {}).get("max_age_days", 14)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    placeholders = ",".join("?" for _ in p1_sources)
    with connect() as connection:
        rows = connection.execute(
            f"""SELECT id,title,summary,url,source,category,published_at,collected_at
            FROM articles WHERE duplicate_of IS NULL AND view = 1
            AND source IN ({placeholders})
            AND COALESCE(first_seen_at,collected_at) > ?
            ORDER BY COALESCE(published_at,collected_at) DESC LIMIT ?""",
            (*p1_sources, cutoff, top_n),
        ).fetchall()
    return [dict(row) for row in rows]


def _select_node(_state: SummaryState) -> SummaryState:
    signals = _new_p1_signals()
    _progress(f"Sélection des signaux P1 : {len(signals)} trouvé(s)", 1, 6)
    return {"signals": signals}


def _source_block(
    new_signals: list[dict[str, Any]], related: list[dict[str, Any]]
) -> str:
    return "\n\n".join(
        f"[{index}] [{label}] {item['title']}\n"
        f"Source: {item['source']} · {item['url']}\n"
        f"{str(item.get('summary') or '')[:1600]}"
        for index, (label, item) in enumerate(
            [
                *(("NOUVEAU", item) for item in new_signals),
                *(("CONTEXTE", item) for item in related),
            ],
            start=1,
        )
    )


def _references_markdown(
    new_signals: list[dict[str, Any]], related: list[dict[str, Any]]
) -> str:
    lines = []
    for index, (label, item) in enumerate(
        [
            *(("nouveau P1", item) for item in new_signals),
            *(("contexte", item) for item in related),
        ],
        start=1,
    ):
        lines.append(
            f"[{index}] [{item['title']}]({item['url']}) — {item['source']} ({label})"
        )
    return "### Sources\n\n" + "\n\n".join(lines)


def _draft_node(state: SummaryState) -> SummaryState:
    by_id = {signal["id"]: signal for signal in state["signals"]}
    new_signals = list(by_id.values())
    query = "; ".join(signal["title"] for signal in new_signals)
    new_ids = set(by_id)
    _progress("Recherche du contexte global", 3, 6)
    related = [item for item in retrieve(query) if item["id"] not in new_ids]
    instruction = load_prompt(
        "summary",
        "section",
        title="Points clés",
        references=_source_block(new_signals, related),
    )
    _progress("Rédaction du rapport complet par Nyx", 4, 6)
    response = chat_model().invoke(instruction)
    content = (
        f"{str(response.content).strip()}\n\n"
        f"{_references_markdown(new_signals, related)}"
    )
    _progress("Rapport complet rédigé", 5, 6)
    return {"drafts": [{"title": "Points clés", "content": content}]}


def _compose_node(state: SummaryState) -> SummaryState:
    _progress(
        "Assemblage du rapport Markdown",
        5,
        6,
    )
    generated_at = datetime.now(REPORT_TIMEZONE)
    sections = "\n\n".join(
        f"## {draft['title']}\n\n{draft['content'].strip()}"
        for draft in state["drafts"]
    )
    document = (
        f"# Synthèse IA — {generated_at.strftime('%d/%m/%Y %H:%M %Z')}\n\n"
        f"> Générée le {generated_at.isoformat()} à partir de "
        f"{len(state['signals'])} nouveau(x) signal(aux) P1.\n\n{sections}\n"
    )
    return {"document": document, "generated_at": generated_at.isoformat()}


def _save_node(state: SummaryState) -> SummaryState:
    generated_at = datetime.fromisoformat(state["generated_at"])
    archive_path = report_path(SUMMARY_PATH, generated_at)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_temporary = archive_path.with_suffix(".md.tmp")
    archive_temporary.write_text(state["document"], encoding="utf-8")
    archive_temporary.replace(archive_path)

    summary_temporary = SUMMARY_PATH.with_suffix(".md.tmp")
    summary_temporary.write_text(state["document"], encoding="utf-8")
    summary_temporary.replace(SUMMARY_PATH)
    _progress("Rapport sauvegardé", 1, 1)
    return {}


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(SummaryState)
    builder.add_node("select", _select_node)
    builder.add_node("draft_sections", _draft_node)
    builder.add_node("compose", _compose_node)
    builder.add_node("save", _save_node)
    builder.add_edge(START, "select")
    builder.add_conditional_edges(
        "select",
        lambda state: "draft" if state.get("signals") else "done",
        {"draft": "draft_sections", "done": END},
    )
    builder.add_edge("draft_sections", "compose")
    builder.add_edge("compose", "save")
    builder.add_edge("save", END)
    return builder.compile()


def graph():
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = _build_graph()
    return _graph


def generate_summary(
    progress: Callable[[str, str, int, int], None] | None = None,
) -> dict[str, Any]:
    token = _progress_callback.set(progress)
    try:
        result = graph().invoke({})
    finally:
        _progress_callback.reset(token)
    signals = result.get("signals", [])
    return {
        "generated": bool(result.get("document")),
        "signals": len(signals),
        "sections": len(result.get("drafts", [])),
        "planning_mode": "deterministic" if result.get("document") else None,
        "path": str(SUMMARY_PATH),
    }
