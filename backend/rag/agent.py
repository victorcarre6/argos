from __future__ import annotations

import threading
from typing import Any

import requests

from rag.models import chat_model
from rag.prompts import load_prompt
from rag.retrieve import retrieve
from system.settings import load_ai_config

_graph: Any | None = None
_graph_lock = threading.Lock()


def _format_context(sources: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        "[{}] {}\nSource: {} · {}\n{}".format(
            index + 1,
            item["title"],
            item["source"],
            item["url"],
            item["summary"][:1600],
        )
        for index, item in enumerate(sources)
    )


def _build_graph():
    from typing import Annotated, TypedDict

    from langchain_core.messages import SystemMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph, add_messages

    RagState = TypedDict(
        "RagState",
        {
            "messages": Annotated[list[Any], add_messages],
            "question": str,
            "sources": list[dict[str, Any]],
            "context": str,
        },
    )

    def retrieve_node(state: RagState) -> dict[str, Any]:
        sources = retrieve(state["question"], profile="assistant")
        return {"sources": sources, "context": _format_context(sources)}

    def generate_node(state: RagState) -> dict[str, Any]:
        system = SystemMessage(
            content=load_prompt("assistant", "system", context=state["context"])
        )
        history_limit = int(
            load_ai_config()["assistant"]["rag"].get("session_message_limit", 12)
        )
        response = chat_model().invoke([system, *state["messages"][-history_limit:]])
        return {"messages": [response]}

    builder = StateGraph(RagState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder.compile(checkpointer=InMemorySaver())


def graph():
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = _build_graph()
    return _graph


def answer(prompt: str, session_id: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    result = graph().invoke(
        {"messages": [HumanMessage(content=prompt)], "question": prompt},
        {"configurable": {"thread_id": session_id}},
    )
    return {
        "answer": str(result["messages"][-1].content),
        "model": load_ai_config()["assistant"]["model"],
        "sources": result["sources"],
        "session_id": session_id,
    }


def clear_session(session_id: str) -> None:
    graph().checkpointer.delete_thread(session_id)


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
