```text
 ____  ____   ___  __  __ ____ _____ ____   ___ _____
|  _ \|  _ \ / _ \|  \/  |  _ \_   _| __ ) / _ \_   _|
| |_) | |_) | | | | |\/| | |_) || | |  _ \| | | || |
|  __/|  _ <| |_| | |  | |  __/ | | | |_) | |_| || |
|_|   |_| \_\\___/|_|  |_|_|    |_| |____/ \___/ |_|
```

# promptbot

`promptbot` is a local-first terminal tool that rewrites rough ideas into stronger prompts for Claude and other LLMs.

No API keys. No telemetry. Everything runs locally.

## What It Does

- rewrites vague or meta-language into direct, actionable instructions
- filters filler phrases, typos, and conversational noise
- sharpens the goal into a clean `Task:` line
- extracts context, constraints, and output requirements into labeled sections
- outputs a lean directive block: `Task / Context / Rules / Format`
- infers audience and format cues automatically
- supports a stronger second-pass rewrite with `strengthen`
- renders the optimized prompt side-by-side in the terminal

## Install

```bash
git clone https://github.com/ek33450505/promptbot.git
cd promptbot
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs:

- `promptbot`
- `promptopt` as a compatibility alias

## Quick Start

Interactive mode:

```bash
promptbot
```

One-shot mode:

```bash
promptbot "Debug a Python function that fails on empty input"
```

Copy immediately:

```bash
promptbot --copy "Summarize this meeting in 3 bullet points"
```

## Interactive Flow

1. Choose a response style: `lean`, `balanced`, or `expert`
2. Choose an output format: paragraph, bullets, steps, JSON, or custom
3. Paste your prompt and end with a blank line
4. Choose `copy`, `strengthen`, `retry`, or `quit`

Enter `/advanced` at prompt entry to set:

- audience
- must-include guidance
- avoid guidance

## Output Format

Prompts are rewritten into a compact directive block:

```text
Task: <sharpened goal>
Context: <extracted background, if any>
Rules:
1. <constraint or output requirement>
2. ...
Format: <selected format, if any>
```

Sections are only included when they have real content — nothing is padded.

## Example

Input:

```text
I need a strong prompt for Claude to debug a Python function that crashes
when the input list is empty. I want the answer to explain the root cause,
show the fix, and include a small test case that proves the fix works.
```

Output:

```text
Task: Diagnose and fix a Python function that crashes on empty-list input.
Rules:
1. Explain the root cause.
2. Show the fix.
3. Include a small test case that proves the fix works.
```

Messy input example:

```text
rough input:
The prompts that are being returned with the new formatting are really not
very clean - how can we ensure correct grammer and formatting. We seem to
be including random sentences from the inital prompt.

rewritten output:
Task: Ensure correct grammar and formatting.
Rules:
1. Prevent unrelated source sentences from leaking into the final prompt.
```

## Configuration

Create a local config file to set a default mode:

```bash
cp .promptopt.json.example .promptopt.json
```

Supported fields:

- `default_mode` — `auto`, `code`, or `general` (default: `auto`)

## Development

Run tests:

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Run the module directly:

```bash
python -m promptopt
```

## Notes

- `promptbot` only rewrites prompts locally — no network calls
- clipboard copy uses `pbcopy`, `wl-copy`, or `xclip`
- project-local config file is `.promptopt.json`
