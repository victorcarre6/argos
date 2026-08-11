from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypedDict

from pydantic import BaseModel, Field

from feeds.database import connect
from rag.models import chat_model
from rag.prompts import load_prompt
from rag.retrieve import retrieve
from system.settings import SUMMARY_PATH, load_ai_config, load_sources_config, utcnow


class PlannedSection(BaseModel):
    title: str = Field(min_length=1)
    signal_ids: list[str] = Field(default_factory=list)


class SummaryPlan(BaseModel):
    sections: list[PlannedSection] = Field(default_factory=list)


class SummaryState(TypedDict, total=False):
    signals: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    planning_mode: str
    drafts: list[dict[str, str]]
    document: str


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
    if SUMMARY_PATH.exists():
        cutoff = datetime.fromtimestamp(
            SUMMARY_PATH.stat().st_mtime, timezone.utc
        ).isoformat()
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


def _normalize_plan(
    plan: SummaryPlan, signals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {signal["id"]: signal for signal in signals}
    assigned: set[str] = set()
    sections = []
    for proposed in plan.sections[:5]:
        ids = [
            signal_id
            for signal_id in proposed.signal_ids
            if signal_id in by_id and signal_id not in assigned
        ]
        if not ids:
            continue
        assigned.update(ids)
        sections.append({"title": proposed.title.strip(), "signal_ids": ids})

    remaining = [signal_id for signal_id in by_id if signal_id not in assigned]
    if remaining:
        other = next(
            (
                section
                for section in sections
                if section["title"].casefold() == "autres"
            ),
            None,
        )
        if other:
            other["signal_ids"].extend(remaining)
        elif len(sections) < 5:
            sections.append({"title": "Autres", "signal_ids": remaining})
        else:
            displaced = sections.pop()["signal_ids"]
            sections.append({"title": "Autres", "signal_ids": [*displaced, *remaining]})
    return sections or [{"title": "Autres", "signal_ids": list(by_id)}]


def _select_node(_state: SummaryState) -> SummaryState:
    signals = _new_p1_signals()
    _progress(f"Sélection des signaux P1 : {len(signals)} trouvé(s)", 1, 8)
    return {"signals": signals}


def _fallback_plan(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a complete, deterministic plan when structured LLM output fails."""
    groups: dict[str, list[str]] = {}
    for signal in signals:
        groups.setdefault(str(signal.get("category") or "Autres"), []).append(
            signal["id"]
        )
    sections = [
        {"title": title, "signal_ids": signal_ids}
        for title, signal_ids in groups.items()
    ]
    if len(sections) <= 5:
        return sections
    return [
        *sections[:4],
        {
            "title": "Autres",
            "signal_ids": [
                signal_id
                for section in sections[4:]
                for signal_id in section["signal_ids"]
            ],
        },
    ]


def _plan_node(state: SummaryState) -> SummaryState:
    signals = state["signals"]
    catalog = [
        {
            "id": signal["id"],
            "title": signal["title"],
            "source": signal["source"],
            "category": signal["category"],
            "summary": str(signal.get("summary") or "")[:600],
        }
        for signal in signals
    ]
    instruction = load_prompt(
        "summary", "plan", signals=json.dumps(catalog, ensure_ascii=False)
    )
    planner = chat_model().with_structured_output(SummaryPlan, method="json_schema")
    _progress("Planification des thèmes par Nyx", 1, 8)
    try:
        plan = planner.invoke(instruction)
        if not isinstance(plan, SummaryPlan):
            raise ValueError("plan structuré absent")
        result = {
            "sections": _normalize_plan(plan, signals),
            "planning_mode": "llm",
        }
    except Exception:
        result = {
            "sections": _fallback_plan(signals),
            "planning_mode": "fallback",
        }
    _progress(f"Plan prêt : {len(result['sections'])} partie(s)", 2, 8)
    return result


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
    drafts = []
    total = len(state["sections"]) + 4
    for index, section in enumerate(state["sections"], start=1):
        _progress(
            f"Rédaction {index}/{len(state['sections'])} : {section['title']}",
            index + 1,
            total,
        )
        new_signals = [by_id[signal_id] for signal_id in section["signal_ids"]]
        query = f"{section['title']}: " + "; ".join(
            signal["title"] for signal in new_signals
        )
        new_ids = set(section["signal_ids"])
        related = [item for item in retrieve(query) if item["id"] not in new_ids]
        instruction = load_prompt(
            "summary",
            "section",
            title=section["title"],
            references=_source_block(new_signals, related),
        )
        response = chat_model().invoke(instruction)
        drafts.append(
            {
                "title": section["title"],
                "content": (
                    f"{str(response.content).strip()}\n\n"
                    f"{_references_markdown(new_signals, related)}"
                ),
            }
        )
        _progress(f"Partie rédigée {index}/{len(state['sections'])}", index + 2, total)
    return {"drafts": drafts}


def _compose_node(state: SummaryState) -> SummaryState:
    _progress(
        "Assemblage du rapport Markdown",
        len(state["drafts"]) + 2,
        len(state["drafts"]) + 4,
    )
    generated_at = utcnow()
    sections = "\n\n".join(
        f"## {draft['title']}\n\n{draft['content'].strip()}"
        for draft in state["drafts"]
    )
    document = (
        "# Synthèse IA\n\n"
        f"> Générée le {generated_at} à partir de "
        f"{len(state['signals'])} nouveau(x) signal(aux) P1.\n\n{sections}\n"
    )
    return {"document": document}


def _save_node(state: SummaryState) -> SummaryState:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SUMMARY_PATH.with_suffix(".md.tmp")
    temporary.write_text(state["document"], encoding="utf-8")
    temporary.replace(SUMMARY_PATH)
    _progress("Rapport sauvegardé", 1, 1)
    return {}


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(SummaryState)
    builder.add_node("select", _select_node)
    builder.add_node("plan", _plan_node)
    builder.add_node("draft_sections", _draft_node)
    builder.add_node("compose", _compose_node)
    builder.add_node("save", _save_node)
    builder.add_edge(START, "select")
    builder.add_conditional_edges(
        "select",
        lambda state: "plan" if state.get("signals") else "done",
        {"plan": "plan", "done": END},
    )
    builder.add_edge("plan", "draft_sections")
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
        "sections": len(result.get("sections", [])),
        "planning_mode": result.get("planning_mode"),
        "path": str(SUMMARY_PATH),
    }
