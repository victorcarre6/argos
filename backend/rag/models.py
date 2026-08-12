from __future__ import annotations

from system.settings import load_ai_config


def chat_model(
    model: str | None = None,
    *,
    max_output_tokens: int | None = None,
    reasoning: bool | None = None,
):
    from langchain_ollama import ChatOllama

    config = load_ai_config()["assistant"]
    options = {
        "base_url": str(config["url"]),
        "model": model or str(config["model"]),
        "temperature": 0,
        "client_kwargs": {"timeout": int(config.get("timeout_seconds", 180))},
    }
    if max_output_tokens is not None:
        options["num_predict"] = max(1, int(max_output_tokens))
    if reasoning is not None:
        options["reasoning"] = reasoning
    return ChatOllama(
        **options,
    )
