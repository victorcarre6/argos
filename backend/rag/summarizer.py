from __future__ import annotations

import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, TypedDict

from rag.models import chat_model
from rag.prompts import load_prompt
from system.reports import (
    latest_report_path,
    report_generated_at,
    telegram_summary_path,
)
from system.settings import SUMMARY_PATH, load_ai_config


class SummarizerState(TypedDict, total=False):
    report_path: Path
    output_path: Path
    report: str
    title: str
    max_chars: int
    content: str
    reused: bool


_graph: Any | None = None
_progress_callback: ContextVar[Callable[[str, str, int, int], None] | None] = (
    ContextVar("summarizer_progress", default=None)
)


def _progress(label: str, completed: int, total: int) -> None:
    callback = _progress_callback.get()
    if callback:
        callback("summarizer", label, completed, total)


def _load_node(state: SummarizerState) -> SummarizerState:
    report = latest_report_path(SUMMARY_PATH)
    if report is None:
        _progress("Aucun rapport à condenser", 1, 1)
        return {}
    output = telegram_summary_path(SUMMARY_PATH, report)
    if output.exists() and output.stat().st_mtime >= report.stat().st_mtime:
        _progress("Résumé Telegram déjà disponible", 1, 1)
        return {"report_path": report, "output_path": output, "reused": True}
    generated_at = report_generated_at(report)
    _progress("Chargement du rapport complet", 1, 3)
    return {
        "report_path": report,
        "output_path": output,
        "report": report.read_text(encoding="utf-8"),
        "title": f"Rapport {generated_at.strftime('%d-%m %H:%M')}",
        "reused": False,
    }


def _clean_body(value: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    text = re.sub(r"https?://\S+", "", value)
    text = re.sub(r"\[(?:\d+(?:\s*,\s*\d+)*)\]", "", text)
    text = re.sub(
        r"^\s{0,3}(?:#{1,6}|>|[-*+]\s+|\d+[.)]\s+)", "", text, flags=re.MULTILINE
    )
    text = text.replace("*", "").replace("__", "").replace("`", "")
    paragraphs = [
        re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text)
    ]
    return "\n\n".join(item for item in paragraphs if item)


def _summarize_node(state: SummarizerState) -> SummarizerState:
    if not state.get("report") or state.get("reused"):
        return {}
    body_limit = state["max_chars"] - len(state["title"]) - 2
    instruction = load_prompt(
        "summarizer", "telegram", max_chars=body_limit, report=state["report"]
    )
    config = load_ai_config()["summarizer"]
    max_output_tokens = max(1, int(config["max_output_tokens"]))
    reasoning = bool(config.get("reasoning", False))
    content = ""
    for attempt in range(3):
        token_budget = max(1, max_output_tokens // (attempt + 1))
        response = chat_model(
            max_output_tokens=token_budget, reasoning=reasoning
        ).invoke(instruction)
        body = _clean_body(str(response.content).strip())
        if not body:
            if attempt < 2:
                _progress(
                    f"Réponse vide, nouvelle tentative ({attempt + 2}/3)",
                    attempt + 2,
                    4,
                )
                continue
            raise RuntimeError(
                "Nyx a produit trois réponses Telegram vides malgré reasoning=false"
            )
        content = f"{state['title']}\n\n{body}"
        if len(content) <= state["max_chars"]:
            break
        if attempt < 2:
            _progress(f"Condensation supplémentaire ({attempt + 2}/3)", attempt + 2, 4)
        instruction = load_prompt(
            "summarizer", "telegram", max_chars=body_limit, report=body
        )
    if len(content) > state["max_chars"]:
        raise RuntimeError(
            "Nyx n'a pas respecté la limite Telegram après trois condensations"
        )
    _progress("Rapport condensé pour Telegram", 3, 4)
    return {"content": content}


def _save_node(state: SummarizerState) -> SummarizerState:
    if not state.get("content") or state.get("reused"):
        return {}
    output = state["output_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".txt.tmp")
    temporary.write_text(state["content"], encoding="utf-8")
    temporary.replace(output)
    _progress("Résumé Telegram sauvegardé", 4, 4)
    return {}


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(SummarizerState)
    builder.add_node("load", _load_node)
    builder.add_node("summarize", _summarize_node)
    builder.add_node("save", _save_node)
    builder.add_edge(START, "load")
    builder.add_edge("load", "summarize")
    builder.add_edge("summarize", "save")
    builder.add_edge("save", END)
    return builder.compile()


def graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def generate_telegram_summary(
    max_chars: int,
    progress: Callable[[str, str, int, int], None] | None = None,
) -> dict[str, Any]:
    token = _progress_callback.set(progress)
    try:
        result = graph().invoke({"max_chars": max_chars})
    finally:
        _progress_callback.reset(token)
    output_path = result.get("output_path")
    content = result.get("content", "")
    if not content and output_path and Path(output_path).exists():
        content = Path(output_path).read_text(encoding="utf-8")
    return {
        "generated": bool(result.get("content")),
        "reused": bool(result.get("reused")),
        "path": str(output_path) if output_path else None,
        "chars": len(content),
    }
