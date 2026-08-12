from __future__ import annotations

from string import Formatter
from typing import Any

from system.settings import PROMPT_CONFIG_PATH, load_yaml

REQUIRED_PROMPTS = {
    ("assistant", "system"): {"context"},
    ("retrieval", "query_plan"): {"categories", "sources", "keys", "question"},
    ("summary", "section"): {"title", "references"},
    ("summarizer", "telegram"): {"max_chars", "report"},
}


def validate_prompt_config(config: Any) -> list[str]:
    if not isinstance(config, dict):
        return ["La racine des prompts doit être un objet"]
    errors = []
    for (section, name), expected in REQUIRED_PROMPTS.items():
        prompts = config.get(section)
        template = prompts.get(name) if isinstance(prompts, dict) else None
        if not isinstance(template, str) or not template.strip():
            errors.append(f"{section}.{name} est requis")
            continue
        try:
            fields = {
                field
                for _, field, _, _ in Formatter().parse(template)
                if field is not None
            }
        except ValueError as exc:
            errors.append(f"{section}.{name} est invalide : {exc}")
            continue
        if fields != expected:
            errors.append(
                f"{section}.{name} attend les variables {sorted(expected)}, "
                f"reçu {sorted(fields)}"
            )
    return errors


def load_prompt(section: str, name: str, **values: Any) -> str:
    config = load_yaml(PROMPT_CONFIG_PATH)
    prompts = config.get(section)
    template = prompts.get(name) if isinstance(prompts, dict) else None
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"Prompt manquant ou vide : {section}.{name}")
    try:
        return template.format(**values)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"Variables invalides dans le prompt {section}.{name}: {exc}"
        ) from exc
