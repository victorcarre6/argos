from __future__ import annotations

from system.settings import load_ai_config


def chat_model(model: str | None = None):
    from langchain_ollama import ChatOllama

    config = load_ai_config()["assistant"]
    return ChatOllama(
        base_url=str(config["url"]),
        model=model or str(config["model"]),
        temperature=0,
        client_kwargs={"timeout": int(config.get("timeout_seconds", 180))},
    )
