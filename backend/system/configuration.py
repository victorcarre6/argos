from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from flask import Blueprint, jsonify, request

from feeds.database import connect
from feeds.collection import _source_tags
from rag.prompts import validate_prompt_config
from system.settings import (
    AI_CONFIG_PATH,
    CONFIG_PATH,
    DATABASE_PATH,
    PROMPT_CONFIG_PATH,
    SENTENCES_PATH,
    SOURCE_KEYS,
    TELEGRAM_PATH,
    VIEWS_PATH,
    load_ai_config,
    load_sources_config,
    load_yaml,
)
from system.state import collection_state

blueprint = Blueprint("configuration", __name__)

CONFIG_FILES = {
    "sources": CONFIG_PATH,
    "ai": AI_CONFIG_PATH,
    "telegram": TELEGRAM_PATH,
    "prompt": PROMPT_CONFIG_PATH,
    "sentences": SENTENCES_PATH,
    "views": VIEWS_PATH,
}

VIEW_SORTS = {"published", "collected", "score"}


def validate_views(data: Any) -> list[str]:
    views = data.get("views") if isinstance(data, dict) else None
    if not isinstance(views, list):
        return ["views doit être une liste"]
    if len(views) > 5:
        return ["views accepte au maximum cinq raccourcis"]
    names = [
        str(view.get("name", "")).strip() for view in views if isinstance(view, dict)
    ]
    if len(names) != len(views) or any(not name for name in names):
        return ["chaque raccourci doit posséder un nom non vide"]
    if len(set(names)) != len(names):
        return ["les noms des raccourcis doivent être uniques"]
    for index, view in enumerate(views):
        for field in ("categories", "priorities", "sources", "tags"):
            if not isinstance(view.get(field), list):
                return [f"views[{index}].{field} doit être une liste"]
        if view.get("sort") not in VIEW_SORTS:
            return [f"views[{index}].sort est invalide"]
        if not isinstance(view.get("search"), str):
            return [f"views[{index}].search doit être une chaîne"]
        if not isinstance(view.get("favorites_only"), bool) or not isinstance(
            view.get("compact"), bool
        ):
            return [f"views[{index}] doit définir favorites_only et compact"]
        if any(priority not in {1, 2, 3} for priority in view["priorities"]):
            return [f"views[{index}].priorities est invalide"]
    return []


def validate_sentences(data: Any) -> list[str]:
    sentences = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(sentences, list) or not sentences:
        return ["sentences doit être une liste non vide"]
    if not all(
        isinstance(sentence, str) and sentence.strip() for sentence in sentences
    ):
        return ["chaque phrase doit être une chaîne non vide"]
    return []


def validate(data: Any) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
        return ["categories doit être une liste"]
    errors = []
    retention_days = data.get("storage", {}).get("retention_days")
    if not isinstance(retention_days, int) or retention_days < 1:
        errors.append("storage.retention_days doit être un entier positif")
    max_age_days = data.get("collection", {}).get("max_age_days")
    if not isinstance(max_age_days, int) or max_age_days < 1:
        errors.append("collection.max_age_days doit être un entier positif")
    tags = data.get("tags")
    if not isinstance(tags, dict) or not tags:
        errors.append("tags doit être un objet non vide")
    else:
        for tag, aliases in tags.items():
            if not isinstance(tag, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", tag):
                errors.append("chaque nom de tag doit respecter le snake_case ASCII")
            if (
                not isinstance(aliases, list)
                or not aliases
                or not all(
                    isinstance(alias, str) and alias.strip() for alias in aliases
                )
            ):
                errors.append(f"tags.{tag} doit contenir des alias non vides")
    for category_index, category in enumerate(data["categories"]):
        if not isinstance(category, dict) or not str(category.get("name", "")).strip():
            errors.append(f"categories[{category_index}].name est requis")
            continue
        if not isinstance(category.get("sources", []), list):
            errors.append(f"categories[{category_index}].sources doit être une liste")
            continue
        for source_index, source in enumerate(category["sources"]):
            path = f"categories[{category_index}].sources[{source_index}]"
            if not isinstance(source, dict):
                errors.append(f"{path}.name est requis")
                continue
            if not str(source.get("name", "")).strip():
                errors.append(f"{path}.name est requis")
            parsed_url = urlparse(str(source.get("url", "")))
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                errors.append(f"{path}.url doit être une URL HTTP(S)")
            keys = source.get("keys")
            if (
                not isinstance(keys, list)
                or not keys
                or not all(isinstance(key, str) and key in SOURCE_KEYS for key in keys)
            ):
                errors.append(
                    f"{path}.keys doit contenir uniquement les clés autorisées"
                )
            if source.get("priorité") not in {1, 2, 3}:
                errors.append(f"{path}.priorité doit valoir 1, 2 ou 3")
            source_tags = _source_tags(source)
            if not source_tags:
                errors.append(f"{path} doit hériter d'au moins un tag")
            elif any(tag not in tags for tag in source_tags):
                errors.append(f"{path}.tags contient un tag hors taxonomie")
    return errors


@blueprint.get("/api/sources")
def sources() -> Any:
    return jsonify(load_sources_config())


@blueprint.put("/api/sources")
def save_sources() -> Any:
    payload = request.get_json(silent=True)
    errors = validate(payload)
    if errors:
        return jsonify(error="Configuration invalide", details=errors), 400
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    temporary.replace(CONFIG_PATH)
    return jsonify(status="saved")


@blueprint.get("/api/config/<name>")
def config_file(name: str) -> Any:
    path = CONFIG_FILES.get(name)
    if path is None:
        return jsonify(error="Configuration inconnue"), 404
    if not path.exists():
        if name == "sentences":
            return jsonify(name=name, content="sentences: []\n")
        return jsonify(error="Fichier de configuration introuvable"), 404
    return jsonify(name=name, content=path.read_text(encoding="utf-8"))


@blueprint.put("/api/config/<name>")
def save_config_file(name: str) -> Any:
    path = CONFIG_FILES.get(name)
    if path is None:
        return jsonify(error="Configuration inconnue"), 404
    content = (request.get_json(silent=True) or {}).get("content")
    if not isinstance(content, str):
        return jsonify(error="Contenu YAML manquant"), 400
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        return jsonify(error=f"YAML invalide : {exc}"), 400
    if not isinstance(parsed, dict):
        return jsonify(error="La racine YAML doit être un objet"), 400
    if name == "sources":
        errors = validate(parsed)
        if errors:
            return jsonify(error="Configuration invalide", details=errors), 400
    if name == "prompt":
        errors = validate_prompt_config(parsed)
        if errors:
            return jsonify(error="Prompts invalides", details=errors), 400
    if name == "sentences":
        errors = validate_sentences(parsed)
        if errors:
            return jsonify(error="Phrases invalides", details=errors), 400
    if name == "views":
        errors = validate_views(parsed)
        if errors:
            return jsonify(error="Raccourcis invalides", details=errors), 400
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)
    return jsonify(status="saved")


@blueprint.get("/api/views")
def saved_views() -> Any:
    return jsonify(load_yaml(VIEWS_PATH).get("views", []))


@blueprint.post("/api/views")
def add_saved_view() -> Any:
    payload = request.get_json(silent=True)
    views = load_yaml(VIEWS_PATH).get("views", [])
    data = {"views": [*views, payload] if isinstance(views, list) else [payload]}
    errors = validate_views(data)
    if errors:
        return jsonify(error="Raccourci invalide", details=errors), 400
    temporary = VIEWS_PATH.with_suffix(".yaml.tmp")
    temporary.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    temporary.replace(VIEWS_PATH)
    return jsonify(payload), 201


def _jobs_are_running() -> bool:
    return bool(collection_state["running"])


@blueprint.delete("/api/storage/sqlite")
def flush_sqlite() -> Any:
    if _jobs_are_running():
        return jsonify(error="Une collecte est en cours"), 409
    tables = (
        "source_health",
        "articles",
        "rag_index_state",
        "collection_runs",
    )
    with connect() as connection:
        deleted = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
        for table in tables:
            connection.execute(f"DELETE FROM {table}")
    with connect() as connection:
        connection.execute("VACUUM")
        connection.execute(
            "INSERT OR IGNORE INTO rag_index_state (id, pending) VALUES (1, 0)"
        )
    return jsonify(status="flushed", deleted=deleted)


@blueprint.delete("/api/storage/chroma")
def flush_chroma() -> Any:
    if _jobs_are_running():
        return jsonify(error="Une collecte est en cours"), 409
    configured_path = load_ai_config().get("rag", {}).get("chroma_path")
    chroma_path = (
        Path(configured_path) if configured_path else DATABASE_PATH.parent / "chroma"
    )
    if chroma_path.resolve().parent != DATABASE_PATH.parent.resolve():
        return (
            jsonify(error="Le chemin Chroma doit être situé dans le dossier data"),
            400,
        )
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
    return jsonify(status="flushed")
