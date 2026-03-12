from __future__ import annotations

from dataclasses import replace
import shutil
import subprocess
import sys
from pathlib import Path

import click
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from promptopt.config import VALID_MODES, load_config
from promptopt.optimizer import PromptPreferences, optimize_prompt

console = Console()
STARTUP_MIN_WIDTH = 74
STARTUP_MAX_WIDTH = 104
PROMPTBOT_TITLE = r"""
 ____  ____   ___  __  __ ____ _____ ____   ___ _____
|  _ \|  _ \ / _ \|  \/  |  _ \_   _| __ ) / _ \_   _|
| |_) | |_) | | | | |\/| | |_) || | |  _ \| | | || |
|  __/|  _ <| |_| | |  | |  __/ | | | |_) | |_| || |
|_|   |_| \_\\___/|_|  |_|_|    |_| |____/ \___/ |_|
"""


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("prompt_parts", nargs=-1)
@click.option(
    "--mode",
    type=click.Choice(sorted(VALID_MODES)),
    default=None,
    help="Choose prompt mode or leave unset to use config defaults.",
)
@click.option("--copy", is_flag=True, help="Copy the optimized prompt to the clipboard.")
def main(prompt_parts: tuple[str, ...], mode: str | None, copy: bool) -> None:
    """Turn rough prompts into clearer, LLM-ready prompts."""
    try:
        config = load_config(Path.cwd())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    requested_mode = mode or config.default_mode
    prompt_text = read_prompt_text(prompt_parts)

    if prompt_text is None:
        run_interactive(requested_mode)
        return

    result = optimize_prompt(
        prompt_text,
        requested_mode,
        preferences=PromptPreferences(),
    )
    render_result(prompt_text, result.optimized_prompt, result.resolved_mode)

    if copy:
        copy_to_clipboard(result.optimized_prompt)
        console.print("[green]Copied to clipboard.[/green]")


def read_prompt_text(prompt_parts: tuple[str, ...]) -> str | None:
    if prompt_parts:
        return " ".join(prompt_parts).strip()

    if not sys.stdin.isatty():
        piped = click.get_text_stream("stdin").read().strip()
        if piped:
            return piped
        raise click.ClickException("Prompt is empty.")

    return None


def run_interactive(requested_mode: str) -> None:
    show_startup()
    base_preferences = collect_preferences()
    active_preferences = base_preferences
    prompt_text: str | None = None

    while True:
        if prompt_text is None:
            show_prompt_entry()
            prompt_text = collect_interactive_prompt()
            if not prompt_text:
                console.print("[yellow]Prompt is empty. Try again.[/yellow]")
                continue
            if prompt_text.strip().lower() == "/advanced":
                base_preferences = collect_advanced_preferences(base_preferences)
                active_preferences = base_preferences
                prompt_text = None
                continue
            active_preferences = base_preferences

        result = optimize_prompt(
            prompt_text,
            requested_mode,
            preferences=active_preferences,
        )
        render_result(
            prompt_text,
            result.optimized_prompt,
            result.resolved_mode,
            boost_level=active_preferences.boost_level,
        )

        action = ask_numbered_choice(
            "Next step",
            [
                ("copy", "copy optimized prompt to clipboard"),
                ("strengthen", "run a stronger rewrite pass"),
                ("retry", "enter a different prompt"),
                ("quit", "exit without copying"),
            ],
        )

        if action == "copy":
            copy_to_clipboard(result.optimized_prompt)
            console.print("[green]Copied to clipboard.[/green]")
            return
        if action == "strengthen":
            active_preferences = replace(
                active_preferences,
                boost_level=active_preferences.boost_level + 1,
            )
            continue
        if action == "retry":
            prompt_text = None
            active_preferences = base_preferences
            continue
        if action == "quit":
            console.print("[yellow]Exited without copying.[/yellow]")
            return


def collect_preferences() -> PromptPreferences:
    style = ask_numbered_choice(
        "Q1. Response style",
        [
            ("lean", "tight, efficient, and high-signal"),
            ("balanced", "clear detail without overexplaining"),
            ("expert", "deeper, sharper, and more rigorous"),
        ],
    )
    output_format = ask_numbered_choice(
        "Q2. Output format",
        [
            ("short paragraph", "compact prose"),
            ("bullet points", "easy to scan"),
            ("step-by-step", "ordered instructions"),
            ("json", "structured output"),
        ],
        allow_other=True,
    )

    return PromptPreferences(
        brevity=style,
        audience="general",
        output_format=output_format,
    )


def collect_advanced_preferences(preferences: PromptPreferences) -> PromptPreferences:
    console.print(
        Panel.fit(
            "Optional tuning for audience and guardrails.\nLeave text fields blank to skip them.",
            border_style="magenta",
            title="Advanced Setup",
        )
    )
    audience = ask_numbered_choice(
        "Audience",
        [
            ("general", "works for most prompts"),
            ("beginner", "simpler explanations"),
            ("advanced", "more technical depth"),
        ],
        allow_other=True,
    )
    include = console.input("Must include (optional): ").strip()
    avoid = console.input("Avoid (optional): ").strip()
    console.print("[green]Advanced options saved.[/green]\n")
    return replace(
        preferences,
        audience=audience,
        include=include,
        avoid=avoid,
        boost_level=0,
    )


def ask_numbered_choice(
    label: str,
    options: list[tuple[str, str]],
    allow_other: bool = False,
) -> str:
    console.print(f"\n[bold bright_white]{label}[/bold bright_white]")
    for index, (value, description) in enumerate(options, start=1):
        console.print(
            f"  [bold bright_green]{index}.[/bold bright_green] "
            f"[bold white]{value}[/bold white]  [dim]- {description}[/dim]"
        )

    other_index = len(options) + 1
    if allow_other:
        console.print(
            f"  [bold bright_green]{other_index}.[/bold bright_green] "
            "[bold white]other[/bold white]  [dim]- type your own[/dim]"
        )

    while True:
        raw_choice = console.input("[bold bright_green]Select:[/bold bright_green] ").strip()
        if raw_choice.isdigit():
            choice = int(raw_choice)
        else:
            console.print("[yellow]Enter a number from the list.[/yellow]")
            continue

        if 1 <= choice <= len(options):
            return options[choice - 1][0]

        if allow_other and choice == other_index:
            custom_value = console.input("[bold bright_green]Custom value:[/bold bright_green] ").strip()
            if custom_value:
                return custom_value
            console.print("[yellow]Custom value cannot be empty.[/yellow]")
            continue

        console.print("[yellow]Choose one of the listed numbers.[/yellow]")


def show_startup() -> None:
    startup_width = _startup_width()
    hero_text = Text.from_markup(
        "[bold bright_white]Promptbot[/bold bright_white] "
        "[bright_blue]|[/bright_blue] "
        "[bold cyan]The local-first prompt engineering toolkit[/bold cyan]\n\n"
        "[white]Promptbot bridges the gap between rough ideas and production-ready LLM instructions.[/white]\n"
        "[white]High-fidelity rewrites, zero latency, and 100% private. No API keys, no telemetry, just better outputs.[/white]"
    )
    startup_block = Group(
        Align.center(Text(PROMPTBOT_TITLE.strip("\n"), style="bright_white"), width=startup_width),
        Panel(
            hero_text,
            border_style="bright_blue",
            width=startup_width,
        ),
        Align.center("[cyan]local-first prompt engine online[/cyan]", width=startup_width),
        Align.center(
            "[bold]Ready.[/bold] Two quick selections, then your prompt.",
            width=startup_width,
        ),
    )
    console.print(Align.center(startup_block))
    console.print()


def show_prompt_entry() -> None:
    console.print(
        Panel.fit(
            "Paste your rough prompt below.\n"
            "Press Enter on an empty line when you are done.\n"
            "Optional: enter /advanced to set audience and guardrails.",
            border_style="green",
            title="Prompt Entry",
        )
    )
    console.print()


def collect_interactive_prompt() -> str:
    lines: list[str] = []

    while True:
        line = console.input("> " if not lines else "  ")
        if not line.strip():
            break
        lines.append(line)

    return "\n".join(lines).strip()


def render_result(
    source_prompt: str,
    optimized_prompt: str,
    resolved_mode: str,
    boost_level: int = 0,
) -> None:
    console.rule("[bold bright_green]Optimized Prompt[/bold bright_green]")
    console.print(
        Text.assemble(
            ("MODE", "bold bright_green"),
            (": ", "bold bright_green"),
            (resolved_mode, "bold white"),
        )
    )
    if boost_level > 0:
        console.print(
            Text.assemble(
                ("STRENGTH PASS", "bold bright_green"),
                (": ", "bold bright_green"),
                (str(boost_level), "bold white"),
            )
        )
    console.print(
        Columns(
            [
                Panel(
                    source_prompt,
                    title="[bold bright_white]Original Prompt[/bold bright_white]",
                    border_style="bright_blue",
                    expand=True,
                ),
                Panel(
                    _build_prompt_copy_renderable(optimized_prompt),
                    title="[bold bright_green]Prompt to Copy[/bold bright_green]",
                    border_style="bright_green",
                    padding=(1, 2),
                    expand=True,
                ),
            ],
            expand=True,
            equal=True,
        )
    )


def _startup_width() -> int:
    return min(STARTUP_MAX_WIDTH, max(STARTUP_MIN_WIDTH, console.size.width - 6))


def _build_prompt_copy_renderable(optimized_prompt: str) -> Table:
    rows = _extract_render_rows(optimized_prompt)
    label_width = 16
    labels = [label for label, _value in rows if label]
    if labels:
        label_width = max(12, min(16, max(len(label) for label in labels)))

    table = Table.grid(padding=(0, 2), expand=True)
    table.add_column(style="bold bright_green", no_wrap=True, width=label_width, vertical="top")
    table.add_column(style="white", ratio=1, vertical="top")

    for label, value in rows:
        table.add_row(
            Text(label, style="bold bright_green"),
            Text(value, style="white"),
        )

    return table


def _extract_render_rows(optimized_prompt: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    pending_label = ""
    pending_value: list[str] = []

    def flush() -> None:
        nonlocal pending_label, pending_value
        if pending_label or pending_value:
            rows.append((pending_label, "\n".join(pending_value).strip()))
        pending_label = ""
        pending_value = []

    for line in optimized_prompt.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue

        if ":" in stripped:
            colon_idx = stripped.index(":")
            label_candidate = stripped[:colon_idx]
            # A valid label has no spaces and does not start with a digit
            if label_candidate and not label_candidate[0].isdigit() and " " not in label_candidate:
                flush()
                pending_label = label_candidate.upper()
                value = stripped[colon_idx + 1:].strip()
                if value:
                    pending_value = [value]
                continue

        pending_value.append(stripped)

    flush()
    return rows


def copy_to_clipboard(text: str) -> None:
    if shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return

    if shutil.which("wl-copy"):
        subprocess.run(["wl-copy"], input=text, text=True, check=True)
        return

    if shutil.which("xclip"):
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=True,
        )
        return

    raise click.ClickException("No supported clipboard command found.")
