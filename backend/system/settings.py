from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("APP_ROOT", "/app"))
CONFIG_PATH = Path(os.environ.get("SOURCES_CONFIG", ROOT / "config/sources.yml"))
AI_CONFIG_PATH = Path(os.environ.get("AI_CONFIG", ROOT / "config/ai.yaml"))
TELEGRAM_PATH = Path(os.environ.get("TELEGRAM_CONFIG", ROOT / "config/telegram.yaml"))
PROMPT_CONFIG_PATH = Path(os.environ.get("PROMPT_CONFIG", ROOT / "config/prompt.yaml"))
SENTENCES_PATH = Path(
    os.environ.get("SENTENCES_CONFIG", ROOT / "config/sentences.yaml")
)
VIEWS_PATH = Path(os.environ.get("VIEWS_CONFIG", ROOT / "config/views.yaml"))
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "data/monitoring.db"))
SUMMARY_PATH = Path(os.environ.get("SUMMARY_PATH", DATABASE_PATH.parent / "summary.md"))
TIMER_PATH = Path(os.environ.get("TIMER_CONFIG", ROOT / "systemd/argos-collect.timer"))
MAX_ITEMS = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "20"))
STARTED_AT = datetime.now(timezone.utc)

SOURCE_KEYS = {
    "recherche",
    "LLM",
    "IA Agentique",
    "Orchestration",
    "RAG",
    "Cloud",
    "HPC",
    "Deep Learning",
    "Ops",
    "Monitoring",
    "Politique",
    "Newsletter",
    "Cybersécurité",
    "Appels à projets",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_sources_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration introuvable : {CONFIG_PATH}")
    data = load_yaml(CONFIG_PATH)
    data.setdefault("categories", [])
    data.setdefault("storage", {"retention_days": 60})
    data.setdefault("collection", {"max_age_days": 14})
    return data


def _section_with_defaults(
    config: dict[str, Any], name: str, defaults: dict[str, Any]
) -> dict[str, Any]:
    current = config.get(name)
    return {**defaults, **(current if isinstance(current, dict) else {})}


def load_ai_config() -> dict[str, Any]:
    config = load_yaml(AI_CONFIG_PATH)
    config["embedding"] = _section_with_defaults(
        config,
        "embedding",
        {
            "url": "http://192.168.1.11:11434",
            "model": "nomic-embed-text-v2-moe:latest",
        },
    )
    config["assistant"] = _section_with_defaults(
        config,
        "assistant",
        {
            "url": "http://192.168.1.11:11434",
            "model": "qwen3.6:27b",
            "timeout_seconds": 180,
        },
    )
    config["rag"] = _section_with_defaults(
        config,
        "rag",
        {
            "chroma_path": str(DATABASE_PATH.parent / "chroma"),
            "index_limit": 2000,
            "candidate_k": 24,
            "final_k": 6,
            "query_model": "",
            "split_min_chars": 900,
            "chunk_size": 1200,
            "chunk_overlap": 180,
        },
    )
    assistant_rag = config["assistant"].get("rag")
    config["assistant"]["rag"] = {
        "candidate_k": config["rag"]["candidate_k"],
        "final_k": config["rag"]["final_k"],
        "query_model": config["rag"]["query_model"],
        "session_message_limit": 12,
        **(assistant_rag if isinstance(assistant_rag, dict) else {}),
    }
    config["summary"] = _section_with_defaults(
        config,
        "summary",
        {"top_n": 40},
    )
    return config
