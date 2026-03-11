```text
 ____  ____   ___  __  __ ____ _____ ____   ___ _____
|  _ \|  _ \ / _ \|  \/  |  _ \_   _| __ ) / _ \_   _|
| |_) | |_) | | | | |\/| | |_) || | |  _ \| | | || |
|  __/|  _ <| |_| | |  | |  __/ | | | |_) | |_| || |
|_|   |_| \_\\___/|_|  |_|_|    |_| |____/ \___/ |_|
```

# promptbot

`promptbot` is a local-first terminal tool that rewrites rough ideas into stronger prompts for Claude and other LLMs.

It stays intentionally simple: choose a style, choose a format, paste a prompt, review the rewrite, then copy it or strengthen it.

## What It Does

- rewrites vague or meta-language into direct instructions
- filters filler, typos, and admin chatter before building the final prompt
- structures prompts into Claude-friendly XML sections for role, task, context, and instructions
- includes a `role` section only when you explicitly set a persona
- improves technical and general prompts
- infers simple audience and format cues
- supports a stronger second-pass rewrite with `strengthen`
- renders the optimized prompt as a structured, terminal-friendly output block
- formats multi-item sections as readable lists instead of dense joined text
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
3. Make an explicit numbered selection for each prompt
4. Paste your prompt and end with a blank line
5. Choose `copy`, `strengthen`, `retry`, or `quit`
6. Review the original and optimized prompts side-by-side with structured labels in the copy panel

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
<task>
Diagnose and fix a Python function that crashes on empty-list input.
</task>
<instructions>
  <format>
    Use numbered steps, isolate the root cause, show the fix, and end with a verification step.
  </format>
  <style>
    Clear, technically grounded, and implementation-focused.
  </style>
  <deliverables>
    Explain the root cause, show the fix, and include a small test case that proves the fix works.
  </deliverables>
  <quality_bar>
    Use exact technical language, ground the answer in the available evidence, and make the fix immediately actionable. Prefer a general-purpose fix over a narrow workaround that only passes the current test. Keep the solution simple and avoid over-engineering.
  </quality_bar>
</instructions>
```

Prompt quality cleanup example:

```text
rough input:
The prompts that are being returned with the new formatting are really not very clean - how can we ensure correct grammer and formatting. We seem to be including random sentences from the inital prompt.

rewritten output:
<task>
Ensure correct grammar and formatting.
</task>
<instructions>
  <deliverables>
    Prevent unrelated source sentences from leaking into the final prompt.
  </deliverables>
</instructions>
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
- `${role_block}`
- `${audience_xml_block}`
- `${context_xml_block}`
- `${instructions_block}`
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
- interactive selections no longer show suggested default values
