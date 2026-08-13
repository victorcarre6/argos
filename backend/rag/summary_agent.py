from __future__ import annotations

import json
import re
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from random import randint
from typing import Any, Callable, TypedDict

from pydantic import BaseModel, Field

from feeds.database import connect
from rag.models import chat_model
from rag.prompts import load_prompt
from rag.retrieve import retrieve
from system.reports import (
    REPORT_TIMEZONE,
    latest_report_path,
    report_path,
    report_updated_at,
    telegram_part_path,
    telegram_summary_path,
)
from system.settings import (
    SENTENCES_PATH,
    SUMMARY_PATH,
    load_ai_config,
    load_sources_config,
    load_yaml,
)


class PlannedSection(BaseModel):
    title: str = Field(min_length=1)
    overview: str = Field(min_length=1)
    signal_ids: list[str] = Field(default_factory=list)


class SummaryPlan(BaseModel):
    sections: list[PlannedSection] = Field(default_factory=list)


class SummaryState(TypedDict, total=False):
    signals: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    planning_mode: str
    drafts: list[dict[str, Any]]
    document: str
    menu: str
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
    _progress(f"Sélection des signaux P1 : {len(signals)} trouvé(s)", 1, 8)
    return {"signals": signals}


def _normalize_plan(
    plan: SummaryPlan, signals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {signal["id"]: signal for signal in signals}
    assigned: set[str] = set()
    sections = []
    for proposed in plan.sections[:4]:
        ids = [
            signal_id
            for signal_id in proposed.signal_ids
            if signal_id in by_id and signal_id not in assigned
        ]
        if not ids:
            continue
        assigned.update(ids)
        number = len(sections) + 1
        sections.append(
            {
                "number": number,
                "title": proposed.title.strip(),
                "overview": proposed.overview.strip(),
                "signal_ids": ids,
            }
        )
    remaining = [signal_id for signal_id in by_id if signal_id not in assigned]
    other_titles = [by_id[signal_id]["title"] for signal_id in remaining[:2]]
    overview = (
        "Autres signaux observés : " + "; ".join(other_titles) + "."
        if other_titles
        else "Aucun autre signal notable dans cette collecte."
    )
    sections.append(
        {"number": 5, "title": "Autre", "overview": overview, "signal_ids": remaining}
    )
    return sections


def _fallback_plan(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for signal in signals:
        groups.setdefault(str(signal.get("category") or "Autre"), []).append(
            signal["id"]
        )
    proposed = [
        PlannedSection(
            title=title,
            overview="; ".join(
                signal["title"] for signal in signals if signal["id"] in signal_ids[:2]
            ),
            signal_ids=signal_ids,
        )
        for title, signal_ids in list(groups.items())[:4]
    ]
    return _normalize_plan(SummaryPlan(sections=proposed), signals)


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
        sections = _normalize_plan(plan, signals)
        mode = "llm"
    except Exception:
        sections = _fallback_plan(signals)
        mode = "fallback"
    _progress(f"Plan prêt : {len(sections)} partie(s)", 2, 8)
    return {"sections": sections, "planning_mode": mode}


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
    for index, section in enumerate(state["sections"], start=1):
        new_signals = [by_id[signal_id] for signal_id in section["signal_ids"]]
        if not new_signals:
            content = "Aucun autre signal notable dans cette collecte."
        else:
            _progress(
                f"Rédaction {section['number']}. {section['title']}",
                index + 2,
                len(state["sections"]) + 4,
            )
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
            content = f"{str(response.content).strip()}\n\n{_references_markdown(new_signals, related)}"
        drafts.append({**section, "content": content})
    return {"drafts": drafts}


def _plain_text(value: str) -> str:
    text = re.sub(r"\[([^]]+)]\(([^)]+)\)", r"\1 — \2", value)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.replace("**", "").replace("`", "").strip()


def _closing_sentence() -> str:
    configured = load_yaml(SENTENCES_PATH).get("sentences")
    sentences = (
        [
            sentence.strip()
            for sentence in configured
            if isinstance(sentence, str) and sentence.strip()
        ]
        if isinstance(configured, list)
        else []
    )
    return sentences[randint(0, len(sentences) - 1)] if sentences else ""


def _compose_node(state: SummaryState) -> SummaryState:
    generated_at = datetime.now(REPORT_TIMEZONE)
    sections = "\n\n".join(
        f"## {draft['number']}. {draft['title']}\n\n{draft['content'].strip()}"
        for draft in state["drafts"]
    )
    document = (
        f"# Synthèse IA — {generated_at.strftime('%d/%m/%Y %H:%M %Z')}\n\n"
        f"> Générée le {generated_at.isoformat()} à partir de {len(state['signals'])} nouveaux signaux P1.\n\n{sections}\n"
    )
    menu_lines = []
    for draft in state["drafts"]:
        title = re.sub(r"\s+", " ", draft["title"]).strip()[:80]
        overview = re.sub(r"\s+", " ", draft["overview"]).strip()[:280]
        menu_lines.append(f"{draft['number']}. {title}\n{overview}")
    closing_sentence = _closing_sentence()
    prefix = f"{closing_sentence} " if closing_sentence else ""
    menu = "\n\n".join(menu_lines) + (
        f"\n\n{prefix}Réponds le numéro de la partie si tu "
        "souhaites plus d'informations, et /download pour télécharger le rapport complet."
    )
    return {
        "document": document,
        "menu": menu,
        "generated_at": generated_at.isoformat(),
    }


def _save_node(state: SummaryState) -> SummaryState:
    generated_at = datetime.fromisoformat(state["generated_at"])
    archive_path = report_path(SUMMARY_PATH, generated_at)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    files = [
        (archive_path, state["document"]),
        (telegram_summary_path(SUMMARY_PATH, archive_path), state["menu"]),
    ]
    files.extend(
        (
            telegram_part_path(SUMMARY_PATH, archive_path, draft["number"]),
            f"{draft['number']}. {draft['title']}\n\n{_plain_text(draft['content'])}\n",
        )
        for draft in state["drafts"]
    )
    files.append((SUMMARY_PATH, state["document"]))
    for path, content in files:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    _progress("Rapport et parties Telegram sauvegardés", 1, 1)
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
    return {
        "generated": bool(result.get("document")),
        "signals": len(result.get("signals", [])),
        "sections": len(result.get("drafts", [])),
        "planning_mode": result.get("planning_mode"),
        "path": str(SUMMARY_PATH),
    }
