from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import TextIO

from promptopt.config import AppConfig


class ClaudeExecutionError(RuntimeError):
    """Raised when Claude cannot be launched."""


def build_command(
    config: AppConfig,
    model_override: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> list[str]:
    command = shlex.split(config.claude_command)
    if not command:
        raise ClaudeExecutionError("Claude command is empty.")

    command.append("-p")

    effective_model = model_override or config.default_model
    if effective_model:
        command.extend(["--model", effective_model])

    command.extend(config.default_claude_args)
    command.extend(extra_args)
    return command


def describe_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def stream_claude(
    prompt: str,
    config: AppConfig,
    model_override: str | None = None,
    extra_args: tuple[str, ...] = (),
    output_stream: TextIO | None = None,
) -> int:
    command = build_command(
        config=config,
        model_override=model_override,
        extra_args=extra_args,
    )
    _ensure_executable(command[0])

    sink = output_stream or sys.stdout

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise ClaudeExecutionError(
            f"Claude command not found: {command[0]}"
        ) from exc
    except OSError as exc:
        raise ClaudeExecutionError(f"Failed to launch Claude: {exc}") from exc

    if process.stdin is None or process.stdout is None:
        process.kill()
        raise ClaudeExecutionError("Failed to initialize subprocess pipes.")

    try:
        process.stdin.write(prompt)
        if not prompt.endswith("\n"):
            process.stdin.write("\n")
        process.stdin.close()
    except OSError as exc:
        process.kill()
        raise ClaudeExecutionError(f"Failed to send prompt to Claude: {exc}") from exc

    for line in process.stdout:
        sink.write(line)
        sink.flush()

    return process.wait()


def _ensure_executable(executable: str) -> None:
    candidate = Path(executable)
    if candidate.is_absolute() or "/" in executable:
        if not candidate.exists():
            raise ClaudeExecutionError(f"Claude command not found: {executable}")
        return

    if shutil.which(executable) is None:
        raise ClaudeExecutionError(f"Claude command not found on PATH: {executable}")
