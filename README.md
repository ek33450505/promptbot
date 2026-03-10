# promptbot

`promptbot` is a terminal-first prompt optimizer for Claude and other LLMs. It takes rough input, rewrites it into a clearer and more actionable prompt, then lets you review and copy the result locally.

The product is intentionally simple:

1. Launch `promptbot`
2. Pick a style preset
3. Pick an output format
4. Paste a rough prompt
5. Review the optimized version side-by-side
6. Copy it, strengthen it, or try again

`promptbot` does not require an API key and does not send prompts over the network. It rewrites text on your machine so you can paste the result into Claude, Claude Code, or another LLM.

## Highlights

- Fast terminal workflow with a guided but minimal interface
- Stronger prompt rewriting for vague, rough, or meta-language input
- Style presets: `lean`, `balanced`, `expert`
- Output format presets: paragraph, bullets, step-by-step, JSON, or custom
- Side-by-side review of the original and optimized prompt
- Optional advanced tuning via `/advanced`
- Stronger second-pass rewrite via `strengthen`
- Local-only operation
- Project-local template overrides with `.promptopt.json`
- Compatibility alias: `promptopt`

## What It Improves

`promptbot` does more than reformat text. It now:

- removes filler and meta-prompt phrasing
- sharpens vague goals into direct instructions
- infers audience cues when they are obvious
- adds output-specific guidance for bullets, steps, and JSON
- raises the quality bar with clearer deliverables and tighter constraints

Example rough input:

```text
I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty. I want the answer to explain the root cause, show the fix, and include a small test case that proves the fix works.
```

Example optimized output:

```text
Objective: Debug a Python function that crashes when the input list is empty.
Preferred format: step-by-step
Response style: Clear, technically grounded, and implementation-focused.
Output instructions: Use numbered steps, isolate the root cause, show the fix, and end with a verification step.
Quality bar: Resolve ambiguity, use exact technical language, and make the fix immediately actionable.
Requested output: Explain the root cause, show the fix, and include a small test case that proves the fix works.
```

## Requirements

- Python 3.13+
- `pip`
- Clipboard support if you want copy-to-clipboard:
  - macOS: `pbcopy`
  - Linux Wayland: `wl-copy`
  - Linux X11: `xclip`

## Installation

```bash
git clone <repo-url> auto-prompt
cd auto-prompt
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs:

- `promptbot`
- `promptopt` as a compatibility alias

## Quick Start

Run the interactive app:

```bash
promptbot
```

The startup flow is:

1. `Response style`
   - `lean`
   - `balanced`
   - `expert`
2. `Output format`
   - `short paragraph`
   - `bullet points`
   - `step-by-step`
   - `json`
   - `other`
3. Prompt entry
4. Review and action

At prompt entry, paste your request and finish with a blank line.

To open the optional advanced path, enter:

```text
/advanced
```

Advanced mode lets you set:

- audience
- must-include guidance
- avoid guidance

After optimization, choose one of:

- `copy`
- `strengthen`
- `retry`
- `quit`

## Example Startup

```text
         .------.
         | o  o |
         |  --  |
         '------'
          /|__|\
           /  \
        promptbot
```

## Command-Line Usage

Interactive mode:

```bash
promptbot
```

One-shot mode:

```bash
promptbot "Please help me refactor this Python function and add tests"
```

Copy immediately:

```bash
promptbot --copy "Summarize this meeting in 3 bullet points"
```

Pipe input:

```bash
cat prompt.txt | promptbot
```

Force a mode:

```bash
promptbot --mode code "Review src/app.py for bugs"
promptbot --mode general "Write a concise thank-you note"
```

## Review Flow

Interactive mode shows:

- detected mode: `code` or `general`
- the original prompt
- the optimized prompt
- an optional strengthen pass count when you rerun optimization

`strengthen` keeps the same source prompt and reruns the optimizer with a more aggressive rewrite pass.

## Configuration

`promptbot` can load an optional `.promptopt.json` file from the current working directory.

Create one from the sample:

```bash
cp .promptopt.json.example .promptopt.json
```

Only the current directory is checked. Parent directories are not searched.

Supported config fields:

- `default_mode`
- `templates.code`
- `templates.general`

Example config:

```json
{
  "default_mode": "auto",
  "templates": {
    "code": "Objective: $goal\n${persona_block}${audience_block}${format_block}${style_block}${structure_block}${quality_block}${include_block}${avoid_block}${context_block}${constraints_block}${output_block}${reasoning_block}${citation_block}",
    "general": "Objective: $goal\n${persona_block}${audience_block}${format_block}${style_block}${structure_block}${quality_block}${include_block}${avoid_block}${context_block}${constraints_block}${output_block}${reasoning_block}${citation_block}"
  }
}
```

Available template placeholders:

- `$goal`
- `${persona_block}`
- `${audience_block}`
- `${format_block}`
- `${style_block}`
- `${structure_block}`
- `${quality_block}`
- `${include_block}`
- `${avoid_block}`
- `${context_block}`
- `${constraints_block}`
- `${output_block}`
- `${reasoning_block}`
- `${citation_block}`

## Development

Run tests:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Run the module directly:

```bash
python -m promptopt
```

## Project Structure

```text
src/promptopt/cli.py           terminal UX and interactive flow
src/promptopt/optimizer.py     prompt cleanup, inference, and rewrite logic
src/promptopt/config.py        config loading and template defaults
tests/                         unit and CLI coverage
```

## Troubleshooting

`promptbot: command not found`

```bash
source .venv/bin/activate
pip install -e .
```

Clipboard copy fails:

- verify `pbcopy`, `wl-copy`, or `xclip` is installed
- rerun without copy if you only want terminal output

Empty prompt error:

- interactive mode needs at least one non-empty line before the blank line that ends input

## Status

Current version: `0.1.0`

`promptbot` is ready for local prompt rewriting, clipboard workflows, and GitHub publication as a focused terminal tool.
