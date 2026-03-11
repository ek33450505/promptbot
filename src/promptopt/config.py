from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

VALID_MODES = {"auto", "code", "general"}


@dataclass(frozen=True)
class AppConfig:
    claude_command: str
    default_model: str | None
    default_mode: str
    default_claude_args: tuple[str, ...]
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

    return AppConfig(
        claude_command="claude",
        default_model=None,
        default_mode=default_mode,
        default_claude_args=(),
        config_path=config_path,
    )
