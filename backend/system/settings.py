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
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", ROOT / "data/monitoring.db"))
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


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else (default or {})


def load_sources_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration introuvable : {CONFIG_PATH}")
    data = load_yaml(CONFIG_PATH)
    data.setdefault("categories", [])
    data.setdefault("storage", {"retention_days": 180})
    return data


def load_ai_config() -> dict[str, Any]:
    config = load_yaml(AI_CONFIG_PATH)
    config.setdefault(
        "embedding",
        {
            "url": "http://192.168.1.11:11434",
            "model": "nomic-embed-text-v2-moe:latest",
            "batch_size": 16,
            "threshold": 0.62,
        },
    )
    config.setdefault(
        "assistant",
        {
            "url": "http://192.168.1.11:1434",
            "model": "qwen3.6:27b",
            "timeout_seconds": 180,
        },
    )
    return config
