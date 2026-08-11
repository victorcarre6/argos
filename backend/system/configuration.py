from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import yaml
from flask import Blueprint, jsonify, request

from system.settings import CONFIG_PATH, SOURCE_KEYS, load_sources_config

blueprint = Blueprint("configuration", __name__)


def validate(data: Any) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
        return ["categories doit être une liste"]
    errors = []
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
    return errors


@blueprint.get("/api/sources")
def sources() -> Any:
    return jsonify(load_sources_config())


@blueprint.get("/api/sources.yml")
def sources_yaml_file() -> Any:
    return (
        CONFIG_PATH.read_text(encoding="utf-8"),
        200,
        {"Content-Type": "text/yaml; charset=utf-8"},
    )


@blueprint.get("/api/sources/yaml")
def sources_yaml() -> Any:
    return jsonify(content=CONFIG_PATH.read_text(encoding="utf-8"))


@blueprint.put("/api/sources/yaml")
def save_sources_yaml() -> Any:
    content = (request.get_json(silent=True) or {}).get("content")
    if not isinstance(content, str):
        return jsonify(error="Contenu YAML manquant"), 400
    try:
        config = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        return jsonify(error=f"YAML invalide : {exc}"), 400
    errors = validate(config)
    if errors:
        return jsonify(error="Configuration invalide", details=errors), 400
    CONFIG_PATH.write_text(content.rstrip() + "\n", encoding="utf-8")
    return jsonify(ok=True, config=config)


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
