from __future__ import annotations

from dataclasses import dataclass
import re
from string import Template

CODE_HARD_PATTERNS = (
    re.compile(r"```"),
    re.compile(r"(^|\n)\$ [^\n]+"),
    re.compile(r"\bTraceback \(most recent call last\):"),
    re.compile(r"\b(?:src|tests|app|package|pyproject|README)\b[^\n]*\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml|sh|sql|html|css)\b"),
    re.compile(r"\b[A-Za-z0-9_./-]+\.(?:py|js|ts|tsx|jsx|sh|sql|html|css|java|go|rs)\b"),
    re.compile(r"(^|\n)(?:diff --git|@@ |\+\+\+ |--- )"),
)

CODE_SOFT_KEYWORDS = {
    "api",
    "bash",
    "bug",
    "class",
    "cli",
    "code",
    "debug",
    "exception",
    "file",
    "function",
    "git",
    "json",
    "module",
    "path",
    "python",
    "refactor",
    "regex",
    "repo",
    "script",
    "stack trace",
    "test",
}

CONSTRAINT_PATTERN = re.compile(
    r"\b(?:must|should|need to|needs to|required|without|avoid|do not|don't|never|only|keep|limit|under|focus on|exactly|at most)\b",
    re.IGNORECASE,
)
OUTPUT_PATTERN = re.compile(
    r"\b(?:return|respond|response|output|show|list|summarize|format|write|give me|reply|explain|include|provide|walk through)\b",
    re.IGNORECASE,
)
BEGINNER_AUDIENCE_PATTERN = re.compile(
    r"\b(?:beginner|novice|new to|kid|child|middle school|high school|student|non-technical)\b",
    re.IGNORECASE,
)
ADVANCED_AUDIENCE_PATTERN = re.compile(
    r"\b(?:advanced|expert|senior|staff|principal|phd|graduate|technical audience)\b",
    re.IGNORECASE,
)
STYLE_ALIASES = {
    "concise": "lean",
    "standard": "balanced",
    "extended": "expert",
}
COMMON_TYPO_REPLACEMENTS = (
    (r"\brealy\b", "really"),
    (r"\bfiggure\b", "figure"),
    (r"\benginering\b", "engineering"),
    (r"\btommorow\b", "tomorrow"),
    (r"\bclaude\b", "Claude"),
    (r"\bpython\b", "Python"),
    (r"\bjson\b", "JSON"),
    (r"\bapi\b", "API"),
    (r"\bllm\b", "LLM"),
)
COMMON_PHRASE_REPLACEMENTS = (
    (r"\bat random\b", "intermittently"),
    (r"\bafter we deploy\b", "after deployment"),
    (r"\bwhen the input list is empty\b", "on empty-list input"),
    (r"\bpossible root cause\b", "likely root causes"),
    (r"\blook at\b", "Analyze"),
    (r"\btell me what to check first\b", "prioritize the first diagnostic checks"),
    (r"\bsuggest the most likely fix\b", "recommend the most likely fix"),
    (r"\bgive me\b", "provide"),
    (r"\bstep by step\b", "step-by-step"),
    (r"\bnot full of fluff\b", "without filler"),
    (r"\binfra\b", "infrastructure"),
    (r"\bnot code\b", "rather than application code"),
)
NON_GOAL_PATTERN = re.compile(
    r"^(?:nice work(?: dude)?|good job|great job|looks good|awesome|thanks|thank you|nice one)[!. ]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OptimizationResult:
    source_prompt: str
    normalized_prompt: str
    requested_mode: str
    resolved_mode: str
    optimized_prompt: str


@dataclass(frozen=True)
class PromptPreferences:
    brevity: str = "balanced"
    persona: str = ""
    audience: str = "general"
    output_format: str = ""
    include: str = ""
    avoid: str = ""
    citations: bool = False
    reasoning: bool = False
    boost_level: int = 0


def normalize_prompt(prompt: str) -> str:
    text = prompt.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    lines: list[str] = []
    in_fence = False
    last_blank = False

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            lines.append(line)
            in_fence = not in_fence
            last_blank = False
            continue

        if in_fence:
            lines.append(line)
            last_blank = stripped == ""
            continue

        if not stripped:
            if lines and not last_blank:
                lines.append("")
            last_blank = True
            continue

        lines.append(_compact_line(stripped))
        last_blank = False

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def detect_mode(prompt: str) -> str:
    normalized = normalize_prompt(prompt)
    for pattern in CODE_HARD_PATTERNS:
        if pattern.search(normalized):
            return "code"

    lowered = normalized.lower()
    score = sum(1 for keyword in CODE_SOFT_KEYWORDS if _has_keyword(lowered, keyword))
    return "code" if score >= 2 else "general"


def optimize_prompt(
    prompt: str,
    requested_mode: str,
    templates: dict[str, str],
    preferences: PromptPreferences | None = None,
) -> OptimizationResult:
    normalized = normalize_prompt(prompt)
    resolved_mode = detect_mode(normalized) if requested_mode == "auto" else requested_mode
    if resolved_mode not in {"code", "general"}:
        raise ValueError(f"Unsupported mode: {resolved_mode}")

    sections = _extract_sections(
        normalized,
        resolved_mode,
        preferences or PromptPreferences(),
    )
    optimized = Template(templates[resolved_mode]).safe_substitute(**sections).strip()

    return OptimizationResult(
        source_prompt=prompt,
        normalized_prompt=normalized,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        optimized_prompt=optimized,
    )


def _compact_line(line: str) -> str:
    bullet_match = re.match(r"^((?:[-*]|\d+\.)\s+)(.*)$", line)
    if bullet_match:
        prefix, body = bullet_match.groups()
        cleaned = re.sub(r"[ \t]+", " ", body).strip()
        return f"{prefix}{_polish_line_text(cleaned)}"
    return _polish_line_text(re.sub(r"[ \t]+", " ", line).strip())


def _extract_sections(
    normalized: str,
    mode: str,
    preferences: PromptPreferences,
) -> dict[str, str]:
    brevity = _normalize_brevity(preferences.brevity)
    audience = _infer_audience(normalized, preferences.audience)
    output_format = _infer_output_format(normalized, preferences.output_format)
    lines = [line for line in (_polish_extracted_line(line) for line in _normalize_for_extraction(normalized)) if line]
    lines = _drop_non_goal_openers(lines)
    goal = lines[0] if lines else "Help with the request below."
    remainder = lines[1:]

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

    return {
        "goal": _refine_goal(goal, mode, preferences.boost_level),
        "context": _join_lines(context_lines),
        "constraints": _join_lines(constraint_lines),
        "output": _join_lines(output_lines),
        "success": "",
        "prompt": normalized,
        "persona_block": _single_line_block("Role", preferences.persona),
        "audience_block": _single_line_block(
            "Target audience",
            "" if audience == "general" else audience,
        ),
        "format_block": _single_line_block("Preferred format", output_format),
        "style_block": _single_line_block(
            "Response style",
            _style_text(brevity, mode),
        ),
        "structure_block": _single_line_block(
            "Output instructions",
            _format_guidance(output_format, mode),
        ),
        "quality_block": _single_line_block(
            "Quality bar",
            _quality_bar(mode, brevity, preferences.boost_level),
        ),
        "include_block": _single_line_block("Key requirement", preferences.include),
        "avoid_block": _single_line_block("Avoid", preferences.avoid),
        "reasoning_block": _single_line_block(
            "Reasoning",
            "Show step-by-step reasoning only when it improves the result." if preferences.reasoning else "",
        ),
        "citation_block": _single_line_block(
            "Source handling",
            "Use reliable citations and clearly state uncertainty when needed." if preferences.citations else "",
        ),
        "context_block": _render_block("Additional context", context_lines),
        "constraints_block": _render_block("Constraints", constraint_lines),
        "output_block": _render_block("Requested output", output_lines),
    }


def _join_lines(lines: list[str]) -> str:
    return "; ".join(lines)


def _render_block(label: str, lines: list[str]) -> str:
    if not lines:
        return ""

    if all("```" not in line for line in lines):
        return f"{label}: {'; '.join(lines)}\n"

    return f"{label}:\n" + "\n".join(lines) + "\n"


def _single_line_block(label: str, value: str) -> str:
    return f"{label}: {value}\n" if value else ""


def _trim_filler(line: str) -> str:
    substitutions = (
        (r"^>\s*", ""),
        (r"^(?:please\s+)+", ""),
        (r"^(?:can|could|would)\s+you\s+", ""),
        (r"^i\s+(?:would\s+like|want|need)\s+you\s+to\s+", ""),
        (r"^help\s+me\s+", ""),
        (r"^i\s+need\s+(?:a\s+)?(?:really\s+)?(?:strong|good|better|clearer|effective)\s+prompt(?:\s+for\s+claude)?\s+to\s+help\s+me\s+(?:figure\s+out|understand)\s+why\s+", "Determine why "),
        (r"^i\s+need\s+(?:a\s+)?(?:strong|good|better|clearer|effective)\s+prompt(?:\s+for\s+claude)?\s+to\s+", ""),
        (r"^i\s+need\s+(?:a\s+)?(?:really\s+)?(?:strong|good|better|clearer|effective)\s+prompt(?:\s+for\s+claude)?\s+to\s+", ""),
        (r"^i\s+need\s+(?:a\s+)?prompt(?:\s+for\s+claude)?\s+to\s+", ""),
        (r"^i\s+want\s+(?:a\s+)?prompt(?:\s+for\s+claude)?\s+to\s+", ""),
        (r"^i\s+need\s+claude\s+to\s+", ""),
        (r"^i\s+want\s+claude\s+to\s+", ""),
        (r"^i\s+want\s+the\s+(?:answer|response)\s+to\s+", ""),
        (r"^the\s+(?:answer|response)\s+should\s+", ""),
        (r"^it\s+should\s+", ""),
        (r"^make\s+sure\s+(?:the\s+answer|the\s+response|it)\s+", ""),
        (r"^i\s+need\s+help\s+with\s+", ""),
        (r"^help\s+with\s+", ""),
        (r"^tell\s+me\s+about\s+", "Explain "),
        (r"^give\s+me\s+", "Provide "),
        (r"^make\s+this\s+better\b[:\-]?\s*", "Improve "),
        (r"^make\s+this\s+clearer\b[:\-]?\s*", "Clarify "),
        (r"^turn\s+this\s+into\s+", "Transform this into "),
    )

    updated = line
    for pattern, replacement in substitutions:
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)

    return updated.strip()


def _refine_goal(goal: str, mode: str, boost_level: int = 0) -> str:
    text = goal.strip()
    lowered = text.lower()

    direct_map = (
        ("explain ", "Provide a clear explanation of "),
        ("summarize ", "Provide a concise summary of "),
        ("describe ", "Provide a focused description of "),
        ("compare ", "Provide a clear comparison of "),
        ("list ", "List "),
        ("write ", "Write "),
        ("create ", "Create "),
        ("tell me about ", "Provide a concise overview of "),
        ("fix ", "Diagnose and fix "),
        ("debug ", "Diagnose and fix "),
        ("improve ", "Improve "),
        ("review ", "Review "),
        ("find out why ", "Determine why "),
        ("determine why ", "Determine why "),
        ("how do i ", "Explain how to "),
        ("how to ", "Explain how to "),
        ("what is ", "Explain "),
        ("provide ", "Provide "),
        ("clarify ", "Clarify "),
        ("transform this into ", "Transform this into "),
    )

    for prefix, replacement in direct_map:
        if lowered.startswith(prefix):
            refined = replacement + text[len(prefix):]
            return _upgrade_goal_tone(refined, boost_level)

    if mode == "code":
        return _upgrade_goal_tone(_sentence_case(f"Debug or complete this technical task: {text}"), boost_level)
    return _upgrade_goal_tone(_sentence_case(f"Provide a clear, well-structured response to: {text}"), boost_level)


def _has_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _style_text(brevity: str, mode: str) -> str:
    if brevity == "expert":
        return "Deep, rigorous, and insight-rich." if mode == "general" else "Rigorous, technically precise, and implementation-focused."
    if brevity == "balanced":
        return "Clear, polished, and moderately detailed." if mode == "general" else "Clear, technically grounded, and implementation-focused."
    return "Lean, polished, and high-signal." if mode == "general" else "Lean, technically precise, and action-oriented."


def _normalize_for_extraction(normalized: str) -> list[str]:
    if "\n" in normalized:
        return [line for line in normalized.splitlines() if line.strip()]

    segments = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", normalized)
        if segment.strip()
    ]
    return segments or [normalized]


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _polish_extracted_line(line: str) -> str:
    cleaned = _trim_filler(line.strip())
    if not cleaned:
        return ""
    if re.match(r"^[a-z]", cleaned) and not re.match(r"^(?:```|\$|[./~]|[A-Za-z0-9_./-]+\()", cleaned):
        return _sentence_case(cleaned)
    return cleaned


def _polish_line_text(line: str) -> str:
    return _polish_plain_language(_trim_filler(_correct_common_typos(line)))


def _normalize_brevity(brevity: str) -> str:
    normalized = (brevity or "balanced").strip().lower()
    return STYLE_ALIASES.get(normalized, normalized)


def _infer_audience(prompt: str, preferred_audience: str) -> str:
    if preferred_audience and preferred_audience != "general":
        return preferred_audience
    if BEGINNER_AUDIENCE_PATTERN.search(prompt):
        return "beginner"
    if ADVANCED_AUDIENCE_PATTERN.search(prompt):
        return "advanced"
    return "general"


def _infer_output_format(prompt: str, selected_format: str) -> str:
    if selected_format:
        return selected_format

    lowered = prompt.lower()
    if "json" in lowered:
        return "json"
    if "step-by-step" in lowered or "step by step" in lowered or "walk me through" in lowered:
        return "step-by-step"
    if "bullet" in lowered or "bullets" in lowered:
        return "bullet points"
    if "paragraph" in lowered:
        return "short paragraph"
    return ""


def _format_guidance(output_format: str, mode: str) -> str:
    lowered = output_format.lower()
    if lowered == "short paragraph":
        return "Use one compact paragraph with no preamble or filler."
    if lowered == "bullet points":
        return "Use short bullet points ordered by importance."
    if lowered == "step-by-step":
        if mode == "code":
            return "Use numbered steps, isolate the root cause, show the fix, and end with a verification step."
        return "Use numbered steps, keep each step concrete, and finish with a concise final recommendation."
    if lowered == "json":
        return "Return valid JSON only with stable keys and no surrounding prose."
    return ""


def _quality_bar(mode: str, brevity: str, boost_level: int) -> str:
    if mode == "code":
        baseline = "Resolve ambiguity, use exact technical language, and make the fix immediately actionable."
    else:
        baseline = "Resolve ambiguity, use precise language, and keep the response immediately useful."

    if brevity == "expert":
        baseline = baseline.replace("immediately useful", "rigorous and insight-rich")
        baseline = baseline.replace("immediately actionable", "rigorous and implementation-ready")
    elif brevity == "lean":
        baseline = baseline.replace("use precise language, and keep the response immediately useful", "stay specific, remove filler, and prioritize signal over preamble")
        baseline = baseline.replace("use exact technical language, and make the fix immediately actionable", "stay exact, remove filler, and prioritize the decisive fix")

    if boost_level > 0:
        baseline += " Push specificity further by sharpening deliverables, assumptions, and constraints."

    return baseline


def _upgrade_goal_tone(goal: str, boost_level: int) -> str:
    if boost_level <= 0:
        return goal

    upgraded = goal
    replacements = (
        ("Provide a clear explanation of ", "Deliver a precise explanation of "),
        ("Provide a concise summary of ", "Deliver a tightly scoped summary of "),
        ("Provide a focused description of ", "Deliver a focused description of "),
        ("Provide a clear comparison of ", "Deliver a clear comparison of "),
        ("Provide a concise overview of ", "Deliver a concise, high-signal overview of "),
        ("Provide a clear, well-structured response to: ", "Deliver a clear, well-structured response to: "),
        ("Debug or complete this technical task: ", "Resolve this technical task with specific, implementation-ready guidance: "),
    )
    for source, target in replacements:
        if upgraded.startswith(source):
            return target + upgraded[len(source):]
    return upgraded


def _correct_common_typos(text: str) -> str:
    corrected = text
    for pattern, replacement in COMMON_TYPO_REPLACEMENTS:
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    return corrected


def _polish_plain_language(text: str) -> str:
    polished = text
    for pattern, replacement in COMMON_PHRASE_REPLACEMENTS:
        polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)
    return polished


def _drop_non_goal_openers(lines: list[str]) -> list[str]:
    if len(lines) > 1 and NON_GOAL_PATTERN.match(lines[0].strip()):
        return lines[1:]
    return lines
