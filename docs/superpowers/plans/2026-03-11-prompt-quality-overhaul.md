# Prompt Quality Overhaul Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the XML template output system with a lean `Task / Context / Rules / Format` directive format that minimizes tokens while sharpening goal, context, and constraint quality.

**Architecture:** Strip `DEFAULT_TEMPLATES` and template merging from `config.py`. Replace `_extract_sections()` + `Template.safe_substitute()` in `optimizer.py` with `_extract_core()` + `_render_directive()`. Simplify `_extract_render_rows()` in `cli.py` to parse the new label-colon format instead of XML.

**Tech Stack:** Python 3.13+, Click, Rich, pytest (unittest)

**Spec:** `docs/superpowers/specs/2026-03-11-prompt-quality-overhaul-design.md`

---

## Chunk 1: Strip template support from config.py

### Task 1: Remove DEFAULT_TEMPLATES and templates from config.py

**Files:**
- Modify: `src/promptopt/config.py`
- Modify: `tests/test_config.py`

The `DEFAULT_TEMPLATES` dict and `AppConfig.templates` field are being removed. The `.promptopt.json` config file will only support `default_mode` going forward. This task must be done before the optimizer refactor so nothing depends on `templates` anymore.

- [ ] **Step 1: Update `test_config.py` — delete the templates test, keep the rest**

Replace the entire file with:

```python
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.config import load_config, locate_config


class ConfigTests(unittest.TestCase):
    def test_locate_config_only_reads_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            config_path = root / ".promptopt.json"
            config_path.write_text("{}", encoding="utf-8")

            self.assertIsNone(locate_config(nested))

    def test_invalid_mode_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".promptopt.json").write_text(
                json.dumps({"default_mode": "invalid"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(root)

    def test_default_mode_loaded_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".promptopt.json").write_text(
                json.dumps({"default_mode": "code"}),
                encoding="utf-8",
            )
            config = load_config(root)
            self.assertEqual(config.default_mode, "code")

    def test_default_mode_is_auto_when_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(Path(temp_dir))
            self.assertEqual(config.default_mode, "auto")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run config tests — expect failure on the templates test, passes on others**

```bash
cd ~/Documents/auto-prompt && source .venv/bin/activate && python -m pytest tests/test_config.py -v
```

Expected: `test_load_config_merges_templates` FAILS (or no longer exists), `test_invalid_mode_raises` and `test_locate_config_only_reads_current_directory` PASS.

- [ ] **Step 3: Rewrite `config.py` — remove DEFAULT_TEMPLATES, remove templates from AppConfig**

Replace the entire file with:

```python
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
```

- [ ] **Step 4: Run config tests — all must pass**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 4 tests PASS. `test_locate_config_only_reads_current_directory`, `test_invalid_mode_raises`, `test_default_mode_loaded_from_config`, `test_default_mode_is_auto_when_no_config`.

- [ ] **Step 5: Commit**

```bash
git add src/promptopt/config.py tests/test_config.py
git commit -m "Remove template system from config — only default_mode configurable"
```

---

## Chunk 2: Replace XML renderer with directive renderer in optimizer.py

### Task 2: Write `_render_directive()` with TDD

**Files:**
- Modify: `src/promptopt/optimizer.py`
- Modify: `tests/test_optimizer.py`

Add the new `_render_directive()` function. This is the core of the overhaul — it replaces all XML block helpers with a single function that assembles the `Task / Context / Rules / Format` directive.

- [ ] **Step 1: Add failing test for `_render_directive()` to `test_optimizer.py`**

Replace the two existing import lines at the top of `test_optimizer.py`:

```python
from promptopt.config import DEFAULT_TEMPLATES
from promptopt.optimizer import PromptPreferences, detect_mode, normalize_prompt, optimize_prompt
```

With this single block:

```python
from promptopt.optimizer import (
    PromptPreferences,
    _render_directive,
    detect_mode,
    normalize_prompt,
    optimize_prompt,
)
```

Add this test class before `OptimizePromptTests`:

```python
class RenderDirectiveTests(unittest.TestCase):
    def test_minimal_directive_has_task_only(self) -> None:
        result = _render_directive(
            goal="Explain recursion.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
        )
        self.assertEqual(result, "Task: Explain recursion.")
        self.assertNotIn("Context:", result)
        self.assertNotIn("Rules:", result)
        self.assertNotIn("Format:", result)

    def test_context_line_appended_when_present(self) -> None:
        result = _render_directive(
            goal="Debug the worker process.",
            context_lines=["Crashes on empty queue"],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="code",
        )
        self.assertIn("Task: Debug the worker process.", result)
        self.assertIn("Context: Crashes on empty queue.", result)

    def test_multiple_context_lines_comma_joined(self) -> None:
        result = _render_directive(
            goal="Debug the worker.",
            context_lines=["Runs on 3 pods", "crashes at peak traffic"],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="code",
        )
        self.assertIn("Context: Runs on 3 pods, crashes at peak traffic.", result)

    def test_constraint_lines_become_numbered_rules(self) -> None:
        result = _render_directive(
            goal="Fix the cache.",
            context_lines=[],
            constraint_lines=["Must not restart pods.", "Avoid full cache flush."],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="code",
        )
        self.assertIn("Rules:", result)
        self.assertIn("1. Must not restart pods.", result)
        self.assertIn("2. Avoid full cache flush.", result)

    def test_output_lines_added_to_rules(self) -> None:
        result = _render_directive(
            goal="Summarize the report.",
            context_lines=[],
            constraint_lines=[],
            output_lines=["Return three bullet points.", "Include a headline."],
            preferences=PromptPreferences(),
            mode="general",
        )
        self.assertIn("Rules:", result)
        self.assertIn("Return three bullet points.", result)
        self.assertIn("Include a headline.", result)

    def test_avoid_preference_adds_rule(self) -> None:
        result = _render_directive(
            goal="Explain DNS.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(avoid="marketing language"),
            mode="general",
        )
        self.assertIn("Rules:", result)
        self.assertIn("Exclude marketing language.", result)

    def test_format_line_present_when_format_set(self) -> None:
        result = _render_directive(
            goal="Debug the crash.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(output_format="step-by-step"),
            mode="code",
        )
        self.assertIn("Format: step-by-step.", result)

    def test_format_line_absent_when_no_format(self) -> None:
        result = _render_directive(
            goal="Explain DNS.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
        )
        self.assertNotIn("Format:", result)

    def test_persona_prepended_as_role_line(self) -> None:
        result = _render_directive(
            goal="Explain recursion.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(persona="expert Python instructor"),
            mode="general",
        )
        self.assertTrue(result.startswith("Role: You are an expert Python instructor."))

    def test_expert_brevity_adds_style_rule(self) -> None:
        result = _render_directive(
            goal="Explain DNS.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(brevity="expert"),
            mode="general",
        )
        self.assertIn("Rules:", result)
        self.assertIn("Use expert depth", result)

    def test_no_xml_tags_in_output(self) -> None:
        result = _render_directive(
            goal="Fix the auth bug.",
            context_lines=["JWT tokens expire too fast"],
            constraint_lines=["Must not break existing sessions."],
            output_lines=["Return the patched function only."],
            preferences=PromptPreferences(
                persona="security engineer",
                brevity="expert",
                output_format="bullet points",
            ),
            mode="code",
        )
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
```

- [ ] **Step 2: Run the new tests — expect ImportError or AttributeError**

```bash
python -m pytest tests/test_optimizer.py::RenderDirectiveTests -v
```

Expected: FAIL — `_render_directive` is not exported from `optimizer.py` yet.

- [ ] **Step 3: Add `_render_directive()` to `optimizer.py`**

Add after the `_role_text()` function (around line 415) and add `from dataclasses import replace` to the imports at the top:

```python
def _render_directive(
    goal: str,
    context_lines: list[str],
    constraint_lines: list[str],
    output_lines: list[str],
    preferences: PromptPreferences,
    mode: str,
) -> str:
    parts: list[str] = []

    if preferences.persona:
        parts.append(f"Role: {_role_text(mode, preferences.persona)}")

    parts.append(f"Task: {goal}")

    if context_lines:
        context = ", ".join(line.rstrip(". ") for line in context_lines)
        parts.append(f"Context: {_finalize_sentence(context)}")

    rules: list[str] = []

    if preferences.audience and preferences.audience != "general":
        rules.append(f"Target a {preferences.audience} audience.")

    rules.extend(constraint_lines)

    if preferences.avoid:
        rules.append(_finalize_sentence(f"Exclude {preferences.avoid}"))

    rules.extend(output_lines)

    if preferences.brevity == "expert":
        if mode == "general":
            rules.append("Use expert depth; be technically precise and insight-rich.")
        else:
            rules.append("Use expert depth; be technically precise and implementation-focused.")

    if preferences.reasoning:
        rules.append("Reason step-by-step internally; present only the final answer.")

    if preferences.citations:
        rules.append("Cite sources for factual claims.")

    if rules:
        numbered = "\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, 1))
        parts.append(f"Rules:\n{numbered}")

    if preferences.output_format:
        parts.append(f"Format: {preferences.output_format}.")

    return "\n".join(parts)
```

- [ ] **Step 4: Run the new tests — all must pass**

```bash
python -m pytest tests/test_optimizer.py::RenderDirectiveTests -v
```

Expected: 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/promptopt/optimizer.py tests/test_optimizer.py
git commit -m "Add _render_directive() — new lean directive output format"
```

---

### Task 3: Wire directive renderer into optimize_prompt() and update all fixtures

**Files:**
- Modify: `src/promptopt/optimizer.py`
- Modify: `src/promptopt/cli.py`
- Modify: `tests/test_optimizer.py`

Replace `_extract_sections()` + `Template.safe_substitute()` with `_extract_core()` + `_render_directive()`. Remove the `templates` parameter from `optimize_prompt()`. Update `cli.py` to stop passing `config.templates`. Update all existing optimizer test assertions to check for directive format instead of XML.

- [ ] **Step 1: Update all existing `OptimizePromptTests` tests to check directive format**

Replace the entire `OptimizePromptTests` class in `tests/test_optimizer.py` with:

```python
class OptimizePromptTests(unittest.TestCase):
    def test_auto_mode_detects_code_mode(self) -> None:
        result = optimize_prompt(
            "Refactor src/app.py and add tests for the failure path.",
            "auto",
        )
        self.assertEqual(result.resolved_mode, "code")
        self.assertIn("Task:", result.optimized_prompt)
        self.assertNotIn("<task>", result.optimized_prompt)
        self.assertNotIn("<role>", result.optimized_prompt)

    def test_general_mode_produces_task_line(self) -> None:
        result = optimize_prompt(
            "Summarize this meeting transcript in three bullets.",
            "general",
        )
        self.assertEqual(result.resolved_mode, "general")
        self.assertIn("Task:", result.optimized_prompt)
        self.assertNotIn("<style>", result.optimized_prompt)

    def test_collects_output_lines_into_rules(self) -> None:
        result = optimize_prompt(
            "Build a small CLI.\nReturn JSON.\nOutput a table to stdout.\nKeep it concise.",
            "general",
        )
        self.assertIn("Task:", result.optimized_prompt)
        self.assertIn("Rules:", result.optimized_prompt)
        self.assertIn("Return JSON.", result.optimized_prompt)
        self.assertIn("Output a table to stdout.", result.optimized_prompt)
        self.assertNotIn("<deliverables>", result.optimized_prompt)

    def test_removes_leading_filler_phrases(self) -> None:
        result = optimize_prompt(
            "Please help me summarize this project.",
            "general",
        )
        self.assertIn("Task: Provide a concise summary of this project.", result.optimized_prompt)

    def test_rewrites_meta_prompt_language_into_direct_request(self) -> None:
        result = optimize_prompt(
            "I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty. I want the answer to explain the root cause, show the fix, and include a small test case that proves the fix works.",
            "code",
        )
        self.assertIn("Task: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertIn("Rules:", result.optimized_prompt)
        self.assertIn("Explain the root cause", result.optimized_prompt)
        self.assertNotIn("I want the answer to", result.optimized_prompt)

    def test_applies_persona_and_preferences(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis.",
            "general",
            preferences=PromptPreferences(
                brevity="expert",
                persona="expert biology teacher",
                audience="beginner",
                output_format="3 bullet points",
                include="light-dependent reactions",
                avoid="history",
                citations=True,
                reasoning=True,
            ),
        )
        self.assertIn("Role: You are an expert biology teacher.", result.optimized_prompt)
        self.assertIn("Task:", result.optimized_prompt)
        self.assertIn("Rules:", result.optimized_prompt)
        self.assertIn("Must include light-dependent reactions.", result.optimized_prompt)
        self.assertIn("Exclude history.", result.optimized_prompt)
        self.assertIn("Format: 3 bullet points.", result.optimized_prompt)
        self.assertNotIn("<audience>", result.optimized_prompt)
        self.assertNotIn("<constraints>", result.optimized_prompt)
        self.assertNotIn("<deliverables>", result.optimized_prompt)

    def test_audience_inferred_from_prompt_appears_in_task(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis to a middle school student.",
            "general",
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("Task:", result.optimized_prompt)
        self.assertNotIn("<audience>", result.optimized_prompt)
        # The middle school context should be preserved in the task line
        self.assertIn("middle school", result.optimized_prompt.lower())

    def test_adds_format_line_for_step_by_step(self) -> None:
        result = optimize_prompt(
            "Debug a Python function that crashes when the input list is empty.",
            "code",
            preferences=PromptPreferences(output_format="step-by-step"),
        )
        self.assertIn("Task: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertIn("Format: step-by-step.", result.optimized_prompt)

    def test_strengthen_pass_upgrades_goal_tone(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis.",
            "general",
            preferences=PromptPreferences(boost_level=1),
        )
        self.assertIn("Task: Deliver a precise explanation of photosynthesis.", result.optimized_prompt)

    def test_ignores_conversational_praise_before_real_request(self) -> None:
        result = optimize_prompt(
            "Nice work dude! One last request before we push. Remove the suggested option from the selection prompt.",
            "general",
        )
        self.assertNotIn("Nice work dude", result.optimized_prompt)
        self.assertIn("Remove the suggested option", result.optimized_prompt)

    def test_coding_prompt_example_gets_cleaner_goal_and_fixed_spelling(self) -> None:
        result = optimize_prompt(
            "I need a realy strong prompt for claude to help me figgure out why our python data pipeline keeps failing at random after we deploy. the logs are messy and sometimes it says timeout and other times memory error. I want claude to look at the possible root cause, tell me what to check first, suggest the most likely fix, and give me a clear step by step plan my enginering team can follow tommorow morning.",
            "code",
            preferences=PromptPreferences(output_format="step-by-step", brevity="expert"),
        )
        self.assertIn("Task: Determine why our Python data pipeline keeps failing intermittently after deployment.", result.optimized_prompt)
        self.assertIn("engineering team can follow tomorrow morning", result.optimized_prompt)
        self.assertNotIn("realy", result.optimized_prompt)
        self.assertNotIn("figgure", result.optimized_prompt)
        self.assertNotIn("enginering", result.optimized_prompt)
        self.assertNotIn("tommorow", result.optimized_prompt)

    def test_strips_blockquote_prefix_from_coding_objective(self) -> None:
        result = optimize_prompt(
            "> I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty.",
            "code",
            preferences=PromptPreferences(boost_level=1),
        )
        self.assertIn("Task: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertNotIn("> I need", result.optimized_prompt)

    def test_quality_feedback_becomes_clean_goal_and_output(self) -> None:
        result = optimize_prompt(
            "The prompts that are being returned with the new formatting are really not very clean - how can we ensure correct grammer and formatting. We seem to be including random sentences from the inital prompt.",
            "general",
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("Task: Ensure correct grammar and formatting.", result.optimized_prompt)
        self.assertIn("Prevent unrelated source sentences from leaking into the final prompt.", result.optimized_prompt)
        self.assertNotIn("grammer", result.optimized_prompt)
        self.assertNotIn("inital", result.optimized_prompt)
        self.assertNotIn("not very clean", result.optimized_prompt)

    def test_selects_actionable_line_instead_of_admin_context(self) -> None:
        result = optimize_prompt(
            "One last request before we push one last time. On the options sections we have a default number set adjacent to the Select [] :. Lets go ahead and get rid of the suggested option here. Additionally, On the Prompt to copy can we add some colors and styling here. Everything is jumbled together and its hard to read.",
            "general",
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("Task: Remove the suggested option.", result.optimized_prompt)
        self.assertIn("Add some colors and styling to the prompt-to-copy panel.", result.optimized_prompt)
        self.assertIn("Improve readability and visual separation.", result.optimized_prompt)
        self.assertIn("Context: The selection prompt currently shows a suggested default number.", result.optimized_prompt)
        self.assertNotIn("One last request before we push", result.optimized_prompt)
        self.assertNotIn("<task>", result.optimized_prompt)
```

- [ ] **Step 2: Run updated optimizer tests — expect failures (templates param missing, XML format)**

```bash
python -m pytest tests/test_optimizer.py::OptimizePromptTests -v
```

Expected: Multiple FAIL — `optimize_prompt()` still expects `templates` arg and returns XML format.

- [ ] **Step 3: Add `_extract_core()` to `optimizer.py` and update `optimize_prompt()`**

Add `from dataclasses import replace` to the imports at the top of `optimizer.py` (skip if already added in Task 2 Step 3).

Add `_extract_core()` immediately before `optimize_prompt()`:

```python
def _extract_core(
    normalized: str,
    mode: str,
    preferences: PromptPreferences,
) -> tuple[str, list[str], list[str], list[str]]:
    lines = [
        line
        for line in (_polish_extracted_line(line) for line in _normalize_for_extraction(normalized))
        if line
    ]
    lines = _drop_non_goal_openers(lines)
    lines = [line for line in lines if not NOISE_PATTERN.match(line)]
    goal, remainder = _select_goal_line(lines)

    context_lines: list[str] = []
    constraint_lines: list[str] = []
    output_lines: list[str] = []

    for line in remainder:
        if CONSTRAINT_PATTERN.search(line):
            constraint_lines.append(line)
        elif OUTPUT_PATTERN.search(line):
            output_lines.append(line)
        else:
            context_lines.append(line)

    if preferences.include:
        output_lines.append(_finalize_sentence(f"Must include {preferences.include}"))

    return _refine_goal(goal, mode, preferences.boost_level), context_lines, constraint_lines, output_lines
```

Replace the existing `optimize_prompt()` function with:

```python
def optimize_prompt(
    prompt: str,
    requested_mode: str,
    preferences: PromptPreferences | None = None,
) -> OptimizationResult:
    normalized = normalize_prompt(prompt)
    resolved_mode = detect_mode(normalized) if requested_mode == "auto" else requested_mode
    if resolved_mode not in {"code", "general"}:
        raise ValueError(f"Unsupported mode: {resolved_mode}")

    prefs = preferences or PromptPreferences()

    inferred_format = _infer_output_format(normalized, prefs.output_format)
    if inferred_format != prefs.output_format:
        prefs = replace(prefs, output_format=inferred_format)

    inferred_audience = _infer_audience(normalized, prefs.audience)
    if inferred_audience != prefs.audience:
        prefs = replace(prefs, audience=inferred_audience)

    goal, context_lines, constraint_lines, output_lines = _extract_core(normalized, resolved_mode, prefs)
    optimized = _render_directive(goal, context_lines, constraint_lines, output_lines, prefs, resolved_mode)

    return OptimizationResult(
        source_prompt=prompt,
        normalized_prompt=normalized,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        optimized_prompt=optimized,
    )
```

The `optimize_prompt()` body above already reflects the tuple return from `_extract_core()`; no separate update to `_render_directive()` is needed.

- [ ] **Step 4: Run all optimizer tests — all must pass**

```bash
python -m pytest tests/test_optimizer.py -v
```

Expected: All tests in `NormalizePromptTests`, `DetectModeTests`, `RenderDirectiveTests`, `OptimizePromptTests` PASS.

If any assertion fails, inspect `result.optimized_prompt` output and adjust the test assertion to match the actual rendered text (the extraction logic is unchanged; only rendering changed).

- [ ] **Step 5: Update `cli.py` — remove `templates` arg from all `optimize_prompt()` calls**

In `src/promptopt/cli.py`, find and update the two `optimize_prompt()` calls:

**In `main()`** — change:
```python
result = optimize_prompt(
    prompt_text,
    requested_mode,
    config.templates,
    preferences=PromptPreferences(),
)
```
To:
```python
result = optimize_prompt(
    prompt_text,
    requested_mode,
    preferences=PromptPreferences(),
)
```

**In `run_interactive()`** — change the signature and call. Find `run_interactive(requested_mode, config.templates)` call in `main()`:
```python
run_interactive(requested_mode, config.templates)
```
Change to:
```python
run_interactive(requested_mode)
```

Find the `run_interactive` function definition:
```python
def run_interactive(requested_mode: str, templates: dict[str, str]) -> None:
```
Change to:
```python
def run_interactive(requested_mode: str) -> None:
```

Find the `optimize_prompt()` call inside `run_interactive()`:
```python
result = optimize_prompt(
    prompt_text,
    requested_mode,
    templates,
    preferences=active_preferences,
)
```
Change to:
```python
result = optimize_prompt(
    prompt_text,
    requested_mode,
    preferences=active_preferences,
)
```

- [ ] **Step 6: Run full test suite — all must pass**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS. If CLI tests fail due to `config.templates` references, trace the error and fix the remaining reference in `cli.py`.

- [ ] **Step 7: Remove dead code from `optimizer.py`**

Delete the following functions that are no longer called (they only served the old XML template system):

- `_extract_sections()` — replaced by `_extract_core()`
- `_join_lines()` — was only used by `_extract_sections()`
- `_render_block()` — only used by `_extract_sections()`
- `_single_line_block()` — only used by `_extract_sections()`
- `_tag_block()` — only used by `_extract_sections()`
- `_tag_list_block()` — only used by `_extract_sections()`
- `_xml_block_from_lines()` — only used by `_extract_sections()`
- `_container_block()` — only used by `_extract_sections()`
- `_style_text()` — no longer added to output
- `_quality_bar()` — no longer added to output
- `_format_guidance()` — Format line now uses `preferences.output_format` directly

Also remove the `from string import Template` import at the top of `optimizer.py`.

- [ ] **Step 8: Run full test suite — confirm no regressions**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/promptopt/optimizer.py src/promptopt/cli.py tests/test_optimizer.py
git commit -m "Replace XML template renderer with lean directive format

- Add _extract_core() and _render_directive() replacing _extract_sections()
- Output format: Task / Context / Rules / Format (no XML)
- Remove dead XML block helpers, _style_text, _quality_bar, _format_guidance
- Remove templates param from optimize_prompt() and run_interactive()"
```

---

## Chunk 3: Simplify CLI row parser

### Task 4: Replace XML row parser with directive row parser in cli.py

**Files:**
- Modify: `src/promptopt/cli.py`
- Modify: `tests/test_cli.py`

Remove `_extract_xml_rows()` and simplify `_extract_render_rows()` to handle the new `Label: value` format. The side-by-side display panel in `render_result()` needs this parser to split the output into labeled rows for the table.

- [ ] **Step 1: Add a failing test for the new `_extract_render_rows()` behavior**

Replace the existing `from promptopt.cli import (...)` block in `test_cli.py` with:

```python
from promptopt.cli import (
    _extract_render_rows,
    ask_numbered_choice,
    collect_advanced_preferences,
    collect_interactive_prompt,
    collect_preferences,
    main,
    read_prompt_text,
)
```

Add this test class at the end of `test_cli.py`:

```python
class ExtractRenderRowsTests(unittest.TestCase):
    def test_single_label_value_line(self) -> None:
        rows = _extract_render_rows("Task: Explain recursion.")
        self.assertEqual(rows, [("TASK", "Explain recursion.")])

    def test_multiple_label_lines(self) -> None:
        prompt = "Task: Fix the cache.\nContext: 3 pods behind LB."
        rows = _extract_render_rows(prompt)
        self.assertEqual(rows[0], ("TASK", "Fix the cache."))
        self.assertEqual(rows[1], ("CONTEXT", "3 pods behind LB."))

    def test_rules_block_collected_under_rules_label(self) -> None:
        prompt = "Task: Fix it.\nRules:\n1. No restarts.\n2. Return one fix only."
        rows = _extract_render_rows(prompt)
        task_row = next(r for r in rows if r[0] == "TASK")
        rules_row = next(r for r in rows if r[0] == "RULES")
        self.assertEqual(task_row, ("TASK", "Fix it."))
        self.assertIn("1. No restarts.", rules_row[1])
        self.assertIn("2. Return one fix only.", rules_row[1])

    def test_role_line_parsed_as_role_label(self) -> None:
        prompt = "Role: You are a senior engineer.\nTask: Fix the auth bug."
        rows = _extract_render_rows(prompt)
        self.assertEqual(rows[0][0], "ROLE")
        self.assertIn("senior engineer", rows[0][1])

    def test_no_xml_parsing(self) -> None:
        prompt = "Task: Fix it.\nContext: pods crash."
        rows = _extract_render_rows(prompt)
        for label, value in rows:
            self.assertNotIn("<", label)
            self.assertNotIn("<", value)
```

- [ ] **Step 2: Run the new tests — expect failures**

```bash
python -m pytest tests/test_cli.py::ExtractRenderRowsTests -v
```

Expected: FAIL — `_extract_render_rows` is not exported from `cli.py` (it's a private function; the import will fail or the behavior won't match).

- [ ] **Step 3: Replace `_extract_xml_rows()` and simplify `_extract_render_rows()` in `cli.py`**

Delete the entire `_extract_xml_rows()` function from `cli.py` (lines ~395–426).

Replace the existing `_extract_render_rows()` function with:

```python
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
```

The function `_extract_render_rows()` is called from `_build_prompt_copy_renderable()` — its name and signature are unchanged, so that call site needs no update. You are replacing the entire body of `_extract_render_rows()` and deleting `_extract_xml_rows()` completely.

- [ ] **Step 4: Run the new CLI row tests — all must pass**

```bash
python -m pytest tests/test_cli.py::ExtractRenderRowsTests -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Run full test suite — all must pass**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS. The existing `test_one_shot_prints_optimized_prompt` should still pass since it checks for `"TASK"` in output, which the new parser produces correctly.

- [ ] **Step 6: Smoke test the CLI manually**

```bash
cd ~/Documents/auto-prompt && source .venv/bin/activate
promptbot "explain how DNS works"
```

Expected: Side-by-side display shows `TASK:` row with sharpened goal, no XML tags visible.

```bash
promptbot "Debug my Python function that crashes when the input list is empty. Must not use global state. Return the fixed function."
```

Expected: `TASK:` row with sharpened goal, `RULES:` block with numbered constraints.

- [ ] **Step 7: Final commit**

```bash
git add src/promptopt/cli.py tests/test_cli.py
git commit -m "Simplify CLI row parser — remove XML parser, handle directive format"
```
