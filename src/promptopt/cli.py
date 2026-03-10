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

from promptopt.config import VALID_MODES, load_config
from promptopt.optimizer import PromptPreferences, optimize_prompt

console = Console()
STARTUP_WIDTH = 86
PROMPTBOT_BANNER = r"""
         .------.
         | o  o |
         |  --  |
         '------'
          /|__|\
           /  \
        promptbot
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
        run_interactive(requested_mode, config.templates)
        return

    result = optimize_prompt(
        prompt_text,
        requested_mode,
        config.templates,
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


def run_interactive(requested_mode: str, templates: dict[str, str]) -> None:
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
            templates,
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
            default=1,
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
        default=2,
    )
    output_format = ask_numbered_choice(
        "Q2. Output format",
        [
            ("short paragraph", "compact prose"),
            ("bullet points", "easy to scan"),
            ("step-by-step", "ordered instructions"),
            ("json", "structured output"),
        ],
        default=1,
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
        default=_audience_default_index(preferences.audience),
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
    default: int = 1,
    allow_other: bool = False,
) -> str:
    console.print(f"\n[bold]{label}[/bold]")
    for index, (value, description) in enumerate(options, start=1):
        console.print(f"  {index}. {value}  [dim]- {description}[/dim]")

    other_index = len(options) + 1
    if allow_other:
        console.print(f"  {other_index}. other  [dim]- type your own[/dim]")

    while True:
        raw_choice = console.input(f"Select [{default}]: ").strip()
        if not raw_choice:
            choice = default
        elif raw_choice.isdigit():
            choice = int(raw_choice)
        else:
            console.print("[yellow]Enter a number from the list.[/yellow]")
            continue

        if 1 <= choice <= len(options):
            return options[choice - 1][0]

        if allow_other and choice == other_index:
            custom_value = console.input("Enter custom value: ").strip()
            if custom_value:
                return custom_value
            console.print("[yellow]Custom value cannot be empty.[/yellow]")
            continue

        console.print("[yellow]Choose one of the listed numbers.[/yellow]")


def show_startup() -> None:
    startup_block = Group(
        Align.center(PROMPTBOT_BANNER.strip("\n"), width=STARTUP_WIDTH),
        Panel(
            "Promptbot converts rough ideas into precise, LLM-ready prompts.\n"
            "Choose a response style and output format, then enter your request.",
            border_style="blue",
            title="Session Setup",
            width=STARTUP_WIDTH,
        ),
        Align.center("[cyan]llm-ready prompt optimization online[/cyan]", width=STARTUP_WIDTH),
        Align.center(
            "[bold]Promptbot is ready.[/bold] Two quick selections, then your prompt.",
            width=STARTUP_WIDTH,
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
    console.rule("[bold]Optimized Prompt[/bold]")
    console.print(f"[bold]Mode:[/bold] {resolved_mode}")
    if boost_level > 0:
        console.print(f"[bold]Strength Pass:[/bold] {boost_level}")
    console.print(
        Columns(
            [
                Panel(source_prompt, title="Original Prompt", expand=True),
                Panel(optimized_prompt, title="Prompt to Copy", expand=True),
            ],
            expand=True,
            equal=True,
        )
    )


def _audience_default_index(audience: str) -> int:
    if audience == "beginner":
        return 2
    if audience == "advanced":
        return 3
    return 1


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
