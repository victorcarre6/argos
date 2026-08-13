from __future__ import annotations

import hashlib
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from system.reports import (
    latest_report_path,
    latest_telegram_summary_path,
    telegram_part_path,
)
from system.settings import SUMMARY_PATH, TELEGRAM_PATH, load_yaml


def _delivery_path() -> Path:
    return SUMMARY_PATH.with_suffix(".telegram.sha256")


def _offset_path() -> Path:
    return SUMMARY_PATH.with_suffix(".telegram.offset")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _delivery_hash(content: str, chat_ids: list[str]) -> str:
    return _content_hash(content + "\n" + "\n".join(chat_ids))


def _report_content() -> str:
    report = latest_telegram_summary_path(SUMMARY_PATH)
    return report.read_text(encoding="utf-8").strip() if report else ""


def _chat_ids(config: dict[str, Any]) -> list[str]:
    configured = config.get("chat_ids")
    values = configured.values() if isinstance(configured, dict) else []
    chat_ids = [str(value).strip() for value in values if str(value).strip()]
    if not chat_ids:
        legacy_chat_id = str(config.get("chat_id", "")).strip()
        chat_ids = [legacy_chat_id] if legacy_chat_id else []
    return list(dict.fromkeys(chat_ids))


def _configuration() -> tuple[dict[str, Any], str, list[str]]:
    config = load_yaml(TELEGRAM_PATH)
    token_name = str(config.get("bot_token_env", "TELEGRAM_BOT_TOKEN"))
    return (
        config,
        os.environ.get(token_name, ""),
        _chat_ids(config),
    )


def telegram_message_limit() -> int:
    config = load_yaml(TELEGRAM_PATH)
    return min(4000, max(500, int(config.get("max_message_chars", 3900))))


def telegram_status() -> dict[str, Any]:
    config, token, chat_ids = _configuration()
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
        "ready": enabled and bool(token) and bool(chat_ids),
        "token_configured": bool(token),
        "chat_configured": bool(chat_ids),
        "recipient_count": len(chat_ids),
        "max_message_chars": telegram_message_limit(),
        "report_pending": bool(content)
        and delivered_hash != _delivery_hash(content, chat_ids),
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


def _post_document(token: str, chat_id: str, path: Path) -> None:
    try:
        with path.open("rb") as document:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": (path.name, document, "text/markdown")},
                timeout=30,
            )
    except (OSError, requests.RequestException):
        raise RuntimeError("Envoi du rapport Telegram impossible") from None
    if not response.ok:
        raise RuntimeError(
            f"Telegram a refusé le fichier (HTTP {response.status_code})"
        )


def _message_chunks(text: str, limit: int) -> list[str]:
    chunks = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        boundary = remaining.rfind("\n\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
        chunks.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    return chunks


def _help_message() -> str:
    return (
        "Argos vous envoie le sommaire du dernier rapport de veille.\n\n"
        "Répondez par un chiffre de 1 à 4 pour lire un thème principal, ou par "
        "5 pour lire la partie Autre. Vous pouvez demander plusieurs parties à "
        "la suite. Les choix pointent toujours vers le rapport le plus récent.\n\n"
        "Envoyez /download pour télécharger le rapport Markdown complet, ou "
        "/help pour afficher de nouveau cette aide."
    )


def _available_parts() -> dict[int, Path]:
    report = latest_report_path(SUMMARY_PATH)
    if report is None:
        return {}
    return {
        number: path
        for number in range(1, 6)
        if (path := telegram_part_path(SUMMARY_PATH, report, number)).exists()
    }


def handle_update(update: dict[str, Any]) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat")
    chat_id = str(chat.get("id", "")).strip() if isinstance(chat, dict) else ""
    _config, token, chat_ids = _configuration()
    if not token or chat_id not in chat_ids:
        return
    text = str(message.get("text", "")).strip()
    command = text.casefold().split("@", 1)[0]
    if command in {"/help", "/start"}:
        _post_message(token, chat_id, _help_message())
        return
    if command == "/download":
        report = latest_report_path(SUMMARY_PATH)
        if report is None:
            _post_message(token, chat_id, "Aucun rapport n'est encore disponible.")
        else:
            _post_document(token, chat_id, report)
        return
    if text not in {"1", "2", "3", "4", "5"}:
        _post_message(
            token,
            chat_id,
            "Commande inconnue. Envoyez /help pour voir les choix disponibles.",
        )
        return
    parts = _available_parts()
    number = int(text)
    if number not in parts:
        available = ", ".join(str(value) for value in parts) or "aucune"
        _post_message(
            token,
            chat_id,
            f"Cette partie n'existe pas dans le dernier rapport. Choix disponibles : {available}.",
        )
        return
    content = parts[number].read_text(encoding="utf-8").strip()
    for chunk in _message_chunks(content, telegram_message_limit()):
        _post_message(token, chat_id, chunk)


def _read_offset() -> int:
    try:
        return int(_offset_path().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _write_offset(offset: int) -> None:
    path = _offset_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".offset.tmp")
    temporary.write_text(str(offset), encoding="utf-8")
    temporary.replace(path)


def poll_updates(stop_event: threading.Event) -> None:
    offset = _read_offset()
    while not stop_event.is_set():
        config, token, chat_ids = _configuration()
        if not config.get("enabled") or not token or not chat_ids:
            stop_event.wait(5)
            continue
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": '["message"]',
                },
                timeout=35,
            )
            response.raise_for_status()
            updates = response.json().get("result", [])
            for update in updates:
                update_id = int(update["update_id"])
                handle_update(update)
                offset = update_id + 1
                _write_offset(offset)
        except (requests.RequestException, ValueError, KeyError, AttributeError):
            stop_event.wait(5)


_listener_stop = threading.Event()
_listener_thread: threading.Thread | None = None


def start_bot_listener() -> None:
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive():
        return
    _listener_thread = threading.Thread(
        target=poll_updates,
        args=(_listener_stop,),
        name="telegram-listener",
        daemon=True,
    )
    _listener_thread.start()


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

    _config, token, chat_ids = _configuration()
    content = _report_content()
    if len(content) > status["max_message_chars"]:
        raise RuntimeError("Le résumé dépasse la limite d'un message Telegram")
    if progress:
        progress("telegram", "Envoi du résumé Telegram", 0, len(chat_ids))
    for index, chat_id in enumerate(chat_ids, start=1):
        _post_message(token, chat_id, content)
        if progress:
            progress(
                "telegram",
                f"Résumé Telegram envoyé ({index}/{len(chat_ids)})",
                index,
                len(chat_ids),
            )

    delivery_path = _delivery_path()
    delivery_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = delivery_path.with_suffix(".sha256.tmp")
    temporary.write_text(_delivery_hash(content, chat_ids), encoding="utf-8")
    temporary.replace(delivery_path)
    return {"sent": True, "reason": None, "messages": len(chat_ids)}
