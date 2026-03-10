# promptbot

`promptbot` is a local-first terminal tool that rewrites rough ideas into stronger prompts for Claude and other LLMs.

It stays intentionally simple: choose a style, choose a format, paste a prompt, review the rewrite, then copy it or strengthen it.

## What It Does

- rewrites vague or meta-language into direct instructions
- improves technical and general prompts
- infers simple audience and format cues
- supports a stronger second-pass rewrite with `strengthen`
- keeps everything local with no API keys or telemetry

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
4. Review the original and optimized prompts side-by-side
5. Choose `copy`, `strengthen`, `retry`, or `quit`

Enter `/advanced` at prompt entry to set:

- audience
- must-include guidance
- avoid guidance

## Example

Input:

```text
I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty. I want the answer to explain the root cause, show the fix, and include a small test case that proves the fix works.
```

Output:

```text
Objective: Debug a Python function that crashes when the input list is empty.
Preferred format: step-by-step
Response style: Clear, technically grounded, and implementation-focused.
Output instructions: Use numbered steps, isolate the root cause, show the fix, and end with a verification step.
Quality bar: Resolve ambiguity, use exact technical language, and make the fix immediately actionable.
Requested output: Explain the root cause, show the fix, and include a small test case that proves the fix works.
```

## Configuration

Create a local config file if you want to override templates:

```bash
cp .promptopt.json.example .promptopt.json
```

Supported fields:

- `default_mode`
- `templates.code`
- `templates.general`

Available placeholders:

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

## Notes

- `promptbot` only rewrites prompts locally
- clipboard copy uses `pbcopy`, `wl-copy`, or `xclip`
- the current project-local config file is `.promptopt.json`
