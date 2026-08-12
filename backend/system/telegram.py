from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from system.reports import latest_telegram_summary_path
from system.settings import SUMMARY_PATH, TELEGRAM_PATH, load_yaml


def _delivery_path() -> Path:
    return SUMMARY_PATH.with_suffix(".telegram.sha256")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _report_content() -> str:
    report = latest_telegram_summary_path(SUMMARY_PATH)
    return report.read_text(encoding="utf-8").strip() if report else ""


def _configuration() -> tuple[dict[str, Any], str, str]:
    config = load_yaml(TELEGRAM_PATH)
    token_name = str(config.get("bot_token_env", "TELEGRAM_BOT_TOKEN"))
    return (
        config,
        os.environ.get(token_name, ""),
        str(config.get("chat_id", "")).strip(),
    )


def telegram_message_limit() -> int:
    config = load_yaml(TELEGRAM_PATH)
    return min(4000, max(500, int(config.get("max_message_chars", 3900))))


def telegram_status() -> dict[str, Any]:
    config, token, chat_id = _configuration()
    enabled = bool(config.get("enabled"))
    delivery_path = _delivery_path()
    content = _report_content()
    delivered_hash = (
        delivery_path.read_text(encoding="utf-8").strip()
        if delivery_path.exists()
        else ""
    )
    return {
        "enabled": enabled,
        "ready": enabled and bool(token) and bool(chat_id),
        "token_configured": bool(token),
        "chat_configured": bool(chat_id),
        "max_message_chars": telegram_message_limit(),
        "report_pending": bool(content) and delivered_hash != _content_hash(content),
        "last_sent_at": (
            datetime.fromtimestamp(
                delivery_path.stat().st_mtime, timezone.utc
            ).isoformat()
            if delivery_path.exists()
            else None
        ),
    }


def _post_message(token: str, chat_id: str, text: str) -> None:
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except requests.RequestException:
        raise RuntimeError("Envoi Telegram impossible") from None
    if not response.ok:
        try:
            description = str(response.json().get("description", "erreur inconnue"))
        except (ValueError, AttributeError):
            description = "erreur inconnue"
        description = description.replace(token, "[secret]")
        raise RuntimeError(
            f"Telegram a refusé le rapport (HTTP {response.status_code}): {description}"
        )


def send_summary_if_pending(
    progress: Callable[[str, str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Deliver the current report once; keep it pending when delivery fails."""
    status = telegram_status()
    if not _report_content():
        if progress:
            progress("telegram", "Aucun rapport à envoyer", 1, 1)
        return {"sent": False, "reason": "no_report", "messages": 0}
    if not status["report_pending"]:
        if progress:
            progress("telegram", "Rapport Telegram déjà envoyé", 1, 1)
        return {"sent": False, "reason": "already_sent", "messages": 0}
    if not status["enabled"]:
        if progress:
            progress("telegram", "Livraison Telegram désactivée", 1, 1)
        return {"sent": False, "reason": "disabled", "messages": 0}
    if not status["ready"]:
        if progress:
            progress("telegram", "Configuration Telegram incomplète", 1, 1)
        return {"sent": False, "reason": "incomplete_configuration", "messages": 0}

    _config, token, chat_id = _configuration()
    content = _report_content()
    if len(content) > status["max_message_chars"]:
        raise RuntimeError("Le résumé dépasse la limite d'un message Telegram")
    if progress:
        progress("telegram", "Envoi du résumé Telegram", 0, 1)
    _post_message(token, chat_id, content)
    if progress:
        progress("telegram", "Résumé Telegram envoyé", 1, 1)

    delivery_path = _delivery_path()
    delivery_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = delivery_path.with_suffix(".sha256.tmp")
    temporary.write_text(_content_hash(content), encoding="utf-8")
    temporary.replace(delivery_path)
    return {"sent": True, "reason": None, "messages": 1}
