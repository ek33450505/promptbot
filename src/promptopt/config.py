from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

VALID_MODES = {"auto", "code", "general"}

DEFAULT_TEMPLATES = {
    "code": (
        "Objective: $goal\n"
        "${persona_block}"
        "${audience_block}"
        "${format_block}"
        "${style_block}"
        "${structure_block}"
        "${quality_block}"
        "${include_block}"
        "${avoid_block}"
        "${context_block}"
        "${constraints_block}"
        "${output_block}"
        "${reasoning_block}"
        "${citation_block}"
    ),
    "general": (
        "Objective: $goal\n"
        "${persona_block}"
        "${audience_block}"
        "${format_block}"
        "${style_block}"
        "${structure_block}"
        "${quality_block}"
        "${include_block}"
        "${avoid_block}"
        "${context_block}"
        "${constraints_block}"
        "${output_block}"
        "${reasoning_block}"
        "${citation_block}"
    ),
}


@dataclass(frozen=True)
class AppConfig:
    claude_command: str
    default_model: str | None
    default_mode: str
    default_claude_args: tuple[str, ...]
    templates: dict[str, str]
    config_path: Path | None = None


def locate_config(start_dir: Path | None = None) -> Path | None:
    current = (start_dir or Path.cwd()).resolve()
    candidate = current / ".promptopt.json"
    return candidate if candidate.is_file() else None


def load_config(start_dir: Path | None = None) -> AppConfig:
    config_path = locate_config(start_dir)
    raw_data: dict[str, object] = {}
    if config_path:
        try:
            raw_data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

        if not isinstance(raw_data, dict):
            raise ValueError(f"{config_path} must contain a JSON object.")

    default_mode = raw_data.get("default_mode", "auto")
    if default_mode not in VALID_MODES:
        raise ValueError("`default_mode` must be one of auto, code, or general.")

    templates = dict(DEFAULT_TEMPLATES)
    template_overrides = raw_data.get("templates", {})
    if template_overrides:
        if not isinstance(template_overrides, dict):
            raise ValueError("`templates` must be an object.")
        for mode, template in template_overrides.items():
            if mode not in {"code", "general"}:
                raise ValueError("`templates` only supports `code` and `general`.")
            if not isinstance(template, str) or not template.strip():
                raise ValueError(f"`templates.{mode}` must be a non-empty string.")
            templates[mode] = template

    return AppConfig(
        claude_command="claude",
        default_model=None,
        default_mode=default_mode,
        default_claude_args=(),
        templates=templates,
        config_path=config_path,
    )
