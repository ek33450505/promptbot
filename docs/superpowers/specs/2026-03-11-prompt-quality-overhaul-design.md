# Promptbot — Prompt Quality Overhaul Design

**Date:** 2026-03-11
**Status:** Approved

---

## Overview

Replace Promptbot's XML-based output template with a lean, directive-style format that minimizes token usage while maximizing prompt precision. The new format uses labeled lines (`Task / Context / Rules / Format`) instead of XML scaffolding, and layers three quality improvements: goal sharpening, context extraction, and constraint framing.

---

## Output Format

The new output format is a compact directive block. Example:

```
You are a senior backend engineer.
Task: Identify and resolve why Redis cache evicts keys under load.
Context: 3-pod service behind a load balancer; cache misses spike at peak traffic.
Rules:
1. No solutions requiring pod restarts.
2. Return root cause and one concrete fix only.
Format: Step-by-step.
```

Rules for inclusion:
- **Role** — only present if persona was set in advanced mode; omitted otherwise
- **Task** — always present; sharpened from the extracted goal line
- **Context** — present only if real context lines were extracted; never padded
- **Rules** — 1–4 numbered items from: constraint lines + `avoid` preference + success criterion inferred from output lines; omitted if none
- **Format** — present only if user selected an output format; omitted otherwise

---

## Architecture

### `config.py`
- Remove `DEFAULT_TEMPLATES` dict
- Remove `templates` field from `AppConfig`
- `.promptopt.json` no longer supports `templates` overrides — only `default_mode` is configurable
- `load_config()` simplified accordingly

### `optimizer.py`
- Remove `Template(...).safe_substitute()` rendering path
- Add `_render_directive(sections, preferences) -> str` — assembles `Task / Context / Rules / Format` block from extracted sections
- **Goal sharpening:** `_refine_goal()` and `_upgrade_goal_tone()` unchanged; output goes into `Task:` line. `boost_level` escalates verb strength (`Provide` → `Deliver`, `Diagnose` → `Identify and resolve`)
- **Context extraction:** Multiple context lines collapsed into one tight comma-joined sentence. Empty → `Context:` line omitted entirely
- **Constraint framing:** Constraint lines + `avoid` preference assembled as numbered `Rules:` list. Success criterion inferred from output lines appended as final rule (e.g. "Return a list only, no surrounding prose")
- `optimize_prompt()` calls `_render_directive()` instead of template substitution
- `_extract_sections()` retained as-is — it already does the extraction work correctly
- `OptimizationResult` struct unchanged

### `cli.py`
- Remove `_extract_xml_rows()` — no longer needed
- Simplify `_extract_render_rows()` to handle only `Label: value` rows and numbered list blocks
- All other CLI logic (interactive flow, startup screen, strengthen, retry, copy) unchanged
- ASCII title / startup screen untouched

---

## Quality Layers

### Goal Sharpening
Existing `_refine_goal()` verb-mapping and `_upgrade_goal_tone()` boost logic retained. The goal always becomes the `Task:` line. `boost_level > 0` (strengthen pass) applies stronger verb upgrades.

### Context Extraction
`_extract_sections()` already separates context lines. In the new renderer, multiple lines are joined with `, ` into a single sentence. If empty, `Context:` is dropped. No fabrication — context only comes from what the user wrote.

### Constraint Framing
Rules are assembled in priority order:
1. Constraint lines detected by `CONSTRAINT_PATTERN` in the prompt
2. `preferences.avoid` if set
3. Success criterion derived from output lines (e.g. output line "return a list" → "Return a list only")

Result is a numbered list under `Rules:`. If there are no rules, the block is omitted.

---

## What Is Not Changing
- Startup screen and ASCII title (`PROMPTBOT_TITLE`)
- Mode detection (`detect_mode`)
- Normalization pipeline (`normalize_prompt`)
- Interactive flow (style/format questions, strengthen, retry, copy)
- Advanced preferences (`collect_advanced_preferences`)
- `PromptPreferences` dataclass
- `OptimizationResult` dataclass
- Test structure (fixtures will need updating to match new output format)

---

## Test Impact
- `tests/test_optimizer.py` — fixture strings need updating to match directive format; test logic unchanged
- `tests/test_cli.py` — `render_result` tests need updated fixture strings; XML row extraction tests removed
- `tests/test_config.py` — tests for `templates` config key removed; `default_mode` tests unchanged
