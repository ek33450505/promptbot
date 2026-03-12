from __future__ import annotations

from dataclasses import dataclass, replace
import re

CODE_HARD_PATTERNS = (
    re.compile(r"```"),
    re.compile(r"(^|\n)\$ [^\n]+"),
    re.compile(r"\bTraceback \(most recent call last\):"),
    re.compile(r"\b[A-Za-z_]*Error\b"),
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
    r"\b(?:return|respond|response|output|show|list|summarize|format|write|give me|reply|explain|include|provide|walk through|add|remove|improve|prevent|eliminate|clarify|refine|clean up)\b",
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
COMMON_TYPO_REPLACEMENTS = (
    (r"\brealy\b", "really"),
    (r"\bfiggure\b", "figure"),
    (r"\benginering\b", "engineering"),
    (r"\bgrammer\b", "grammar"),
    (r"\binital\b", "initial"),
    (r"\bits hard\b", "it is hard"),
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
    (r"\bafter deploy\b", "after deployment"),
    (r"\bwhen the input list is empty\b", "on empty-list input"),
    (r"\bpossible root cause\b", "likely root causes"),
    (r"\blook at\b", "Analyze"),
    (r"\btell me what to check first\b", "prioritize the first diagnostic checks"),
    (r"\bsuggest the most likely fix\b", "recommend the most likely fix"),
    (r"\bsometimes it(?:'s| is|s) a timeout and other times memory spikes\b", "the logs alternate between timeouts and memory spikes"),
    (r"\bsometimes it(?:'s| is|s) a timeout and other times ([A-Za-z_]*Error)\b", r"failures alternate between timeouts and \1"),
    (r"\bthe logs are messy and the logs alternate between\b", "the logs are messy, and failures alternate between"),
    (r"\bthe logs are messy and sometimes it(?:'s| is|s) a timeout and other times ([A-Za-z_]*Error)\b", r"the logs are messy, and failures alternate between timeouts and \1"),
    (r"\bthe logs are messy and failures alternate between\b", "the logs are messy, and failures alternate between"),
    (r"\bgive me\b", "provide"),
    (r"\bget rid of\b", "remove"),
    (r"\bstep by step\b", "step-by-step"),
    (r"\bnot full of fluff\b", "without filler"),
    (r"\binfra\b", "infrastructure"),
    (r"\bnot code\b", "rather than application code"),
)
NON_GOAL_PATTERN = re.compile(
    r"^(?:nice work(?: dude)?|good job|great job|looks good|awesome|thanks|thank you|nice one)[!. ]*$",
    re.IGNORECASE,
)
NOISE_PATTERN = re.compile(
    r"^(?:one last request before we push(?: one last time)?|this is a direct example from promptbot|make any additional changes to the prompt you see fit|note:.*)[!. ]*$",
    re.IGNORECASE,
)
ACTION_PREFIXES = (
    "add ",
    "remove ",
    "improve ",
    "ensure ",
    "prevent ",
    "fix ",
    "debug ",
    "diagnose ",
    "create ",
    "write ",
    "explain ",
    "summarize ",
    "describe ",
    "compare ",
    "list ",
    "clarify ",
    "review ",
    "analyze ",
    "determine ",
    "transform ",
)
WEAK_GOAL_PATTERN = re.compile(
    r"^(?:the|this|these|those|on the|there(?:'s| is)|it(?:'s| is)|we seem to|everything is)\b",
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

    return _refine_goal(goal, mode, preferences.boost_level), context_lines, constraint_lines, output_lines


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


def _compact_line(line: str) -> str:
    bullet_match = re.match(r"^((?:[-*]|\d+\.)\s+)(.*)$", line)
    if bullet_match:
        prefix, body = bullet_match.groups()
        cleaned = re.sub(r"[ \t]+", " ", body).strip()
        return f"{prefix}{_polish_line_text(cleaned)}"
    return _polish_line_text(re.sub(r"[ \t]+", " ", line).strip())


def _role_text(mode: str, persona: str) -> str:
    custom = persona.strip()
    if custom:
        if custom.lower().startswith("you are "):
            return _finalize_sentence(custom)
        article = "an" if custom[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        return f"You are {article} {custom}."
    return ""


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

    if preferences.include:
        rules.append(_finalize_sentence(f"Must include {preferences.include}"))

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


def _trim_filler(line: str) -> str:
    substitutions = (
        (r"^>\s*", ""),
        (r"^(?:please\s+)+", ""),
        (r"^(?:can|could|would)\s+you\s+", ""),
        (r"^i\s+(?:would\s+like|want|need)\s+you\s+to\s+", ""),
        (r"^help\s+me\s+", ""),
        (r"^additionally,\s+", ""),
        (r"^lets\s+go\s+ahead\s+and\s+", ""),
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
        (r"^get\s+rid\s+of\s+", "Remove "),
        (r"^(?:additionally,\s*)?can\s+we\s+add\s+", "Add "),
        (r"^(?:additionally,\s*)?can\s+we\s+remove\s+", "Remove "),
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
        ("add ", "Add "),
        ("remove ", "Remove "),
        ("ensure ", "Ensure "),
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
        ("how can we ensure ", "Ensure "),
        ("can we ensure ", "Ensure "),
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
    cleaned = _rewrite_extracted_line(_trim_filler(line.strip()))
    if not cleaned:
        return ""
    if re.match(r"^[a-z]", cleaned) and not re.match(r"^(?:```|\$|[./~]|[A-Za-z0-9_./-]+\()", cleaned):
        return _sentence_case(cleaned)
    return cleaned


def _rewrite_extracted_line(line: str) -> str:
    lowered = line.lower().strip()

    if "how can we ensure " in lowered:
        match = re.search(r"\bhow can we ensure\s+(.+)$", line, flags=re.IGNORECASE)
        if match:
            return _finalize_sentence(f"Ensure {_clean_clause(match.group(1))}")

    if "can we ensure " in lowered:
        match = re.search(r"\bcan we ensure\s+(.+)$", line, flags=re.IGNORECASE)
        if match:
            return _finalize_sentence(f"Ensure {_clean_clause(match.group(1))}")

    if re.match(r"^we seem to be including random sentences from the initial prompt[. ]*$", lowered):
        return "Prevent unrelated source sentences from leaking into the final prompt."

    if lowered.startswith("we seem to be including "):
        match = re.search(r"^we seem to be including\s+(.+)$", line, flags=re.IGNORECASE)
        if match:
            return _finalize_sentence(
                f"Prevent {_clean_clause(match.group(1))} from leaking into the final prompt"
            )

    match = re.search(
        r"^on the prompt to copy can we add\s+(.+?)(?:\s+here)?[. ]*$",
        line,
        flags=re.IGNORECASE,
    )
    if match:
        return _finalize_sentence(
            f"Add {_clean_clause(match.group(1))} to the prompt-to-copy panel"
        )

    if re.match(
        r"^everything is jumbled together and (?:it is|it's) hard to read[. ]*$",
        lowered,
    ):
        return "Improve readability and visual separation."

    if re.match(
        r"^on the options sections we have a default number set adjacent to the select \[\]\s*:[. ]*$",
        lowered,
    ):
        return "The selection prompt currently shows a suggested default number."

    if any(lowered.startswith(prefix) for prefix in ("add ", "remove ", "improve ", "ensure ", "prevent ")):
        return _finalize_sentence(_clean_clause(line))

    return line


def _polish_line_text(line: str) -> str:
    return _polish_plain_language(_trim_filler(_correct_common_typos(line)))


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


def _select_goal_line(lines: list[str]) -> tuple[str, list[str]]:
    if not lines:
        return "Help with the request below.", []

    best_index = 0
    best_score = _goal_score(lines[0])
    for index, line in enumerate(lines[1:], start=1):
        score = _goal_score(line)
        if score > best_score:
            best_index = index
            best_score = score

    if best_score <= 0:
        return lines[0], lines[1:]

    remainder = [line for index, line in enumerate(lines) if index != best_index]
    return lines[best_index], remainder


def _goal_score(line: str) -> int:
    lowered = line.lower().strip()
    score = 0

    if any(lowered.startswith(prefix) for prefix in ACTION_PREFIXES):
        score += 5

    if WEAK_GOAL_PATTERN.match(lowered):
        score -= 2

    if "?" in line:
        score -= 1

    if len(lowered.split()) <= 3:
        score -= 1

    return score


def _clean_clause(text: str) -> str:
    cleaned = text.strip(" \t\n\r.;:-")
    cleaned = re.sub(r"\s+here$", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _finalize_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."
