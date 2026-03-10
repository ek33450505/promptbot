from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.config import DEFAULT_TEMPLATES
from promptopt.optimizer import PromptPreferences, detect_mode, normalize_prompt, optimize_prompt


class NormalizePromptTests(unittest.TestCase):
    def test_preserves_code_fences(self) -> None:
        prompt = "Fix this.\n\n```python\nprint(  1 )\n```\n"
        normalized = normalize_prompt(prompt)
        self.assertIn("```python", normalized)
        self.assertIn("print(  1 )", normalized)

    def test_collapses_extra_spaces_outside_code(self) -> None:
        prompt = "Summarize   this   text.\n\nKeep   it short."
        normalized = normalize_prompt(prompt)
        self.assertEqual(normalized, "Summarize this text.\n\nKeep it short.")

    def test_corrects_common_typos_and_proper_nouns(self) -> None:
        prompt = "realy figgure out why our python job fails tommorow for the enginering team"
        normalized = normalize_prompt(prompt)
        self.assertIn("really", normalized)
        self.assertIn("figure", normalized)
        self.assertIn("Python", normalized)
        self.assertIn("tomorrow", normalized)
        self.assertIn("engineering", normalized)


class DetectModeTests(unittest.TestCase):
    def test_detects_code_prompt_from_stack_trace(self) -> None:
        prompt = "Traceback (most recent call last):\nValueError: boom"
        self.assertEqual(detect_mode(prompt), "code")

    def test_detects_general_prompt(self) -> None:
        prompt = "Write a concise thank-you note for a colleague."
        self.assertEqual(detect_mode(prompt), "general")

    def test_does_not_match_repo_inside_report(self) -> None:
        prompt = "Make this bug report clearer."
        self.assertEqual(detect_mode(prompt), "general")


class OptimizePromptTests(unittest.TestCase):
    def test_auto_mode_uses_code_template(self) -> None:
        result = optimize_prompt(
            "Refactor src/app.py and add tests for the failure path.",
            "auto",
            DEFAULT_TEMPLATES,
        )
        self.assertEqual(result.resolved_mode, "code")
        self.assertIn("Objective:", result.optimized_prompt)
        self.assertIn("Response style: Clear, technically grounded, and implementation-focused.", result.optimized_prompt)
        self.assertIn("Quality bar:", result.optimized_prompt)

    def test_general_mode_uses_general_template(self) -> None:
        result = optimize_prompt(
            "Summarize this meeting transcript in three bullets.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertEqual(result.resolved_mode, "general")
        self.assertIn("Response style: Clear, polished, and moderately detailed.", result.optimized_prompt)

    def test_collects_multiple_output_lines(self) -> None:
        result = optimize_prompt(
            "Build a small CLI.\nReturn JSON.\nOutput a table to stdout.\nKeep it concise.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("Requested output:", result.optimized_prompt)
        self.assertIn("Return JSON.", result.optimized_prompt)
        self.assertIn("Output a table to stdout.", result.optimized_prompt)

    def test_removes_leading_filler_phrases(self) -> None:
        result = optimize_prompt(
            "Please help me summarize this project.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("Objective: Provide a concise summary of this project.", result.optimized_prompt)

    def test_rewrites_meta_prompt_language_into_direct_request(self) -> None:
        result = optimize_prompt(
            "I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty. I want the answer to explain the root cause, show the fix, and include a small test case that proves the fix works.",
            "code",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("Objective: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertIn("Requested output:", result.optimized_prompt)
        self.assertIn("Explain the root cause", result.optimized_prompt)
        self.assertNotIn("I want the answer to", result.optimized_prompt)

    def test_applies_preferences_to_output(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis.",
            "general",
            DEFAULT_TEMPLATES,
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
        self.assertIn("Role: expert biology teacher", result.optimized_prompt)
        self.assertIn("Target audience: beginner", result.optimized_prompt)
        self.assertIn("Preferred format: 3 bullet points", result.optimized_prompt)
        self.assertIn("Key requirement: light-dependent reactions", result.optimized_prompt)
        self.assertIn("Avoid: history", result.optimized_prompt)
        self.assertIn("Quality bar:", result.optimized_prompt)
        self.assertIn("Source handling:", result.optimized_prompt)
        self.assertIn("Reasoning:", result.optimized_prompt)

    def test_infers_beginner_audience_from_prompt(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis to a middle school student.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("Target audience: beginner", result.optimized_prompt)

    def test_adds_step_by_step_guidance_for_code_prompts(self) -> None:
        result = optimize_prompt(
            "Debug a Python function that crashes when the input list is empty.",
            "code",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="step-by-step"),
        )
        self.assertIn("Objective: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertIn("Output instructions: Use numbered steps, isolate the root cause, show the fix, and end with a verification step.", result.optimized_prompt)

    def test_strengthen_pass_upgrades_goal_tone(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(boost_level=1),
        )
        self.assertIn("Objective: Deliver a precise explanation of photosynthesis.", result.optimized_prompt)
        self.assertIn("Push specificity further", result.optimized_prompt)

    def test_ignores_conversational_praise_before_real_request(self) -> None:
        result = optimize_prompt(
            "Nice work dude! One last request before we push. Remove the suggested option from the selection prompt.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertNotIn("Nice work dude", result.optimized_prompt)
        self.assertIn("Remove the suggested option", result.optimized_prompt)

    def test_coding_prompt_example_gets_cleaner_goal_and_fixed_spelling(self) -> None:
        result = optimize_prompt(
            "I need a realy strong prompt for claude to help me figgure out why our python data pipeline keeps failing at random after we deploy. the logs are messy and sometimes it says timeout and other times memory error. I want claude to look at the possible root cause, tell me what to check first, suggest the most likely fix, and give me a clear step by step plan my enginering team can follow tommorow morning.",
            "code",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="step-by-step", brevity="expert"),
        )
        self.assertIn("Objective: Determine why our Python data pipeline keeps failing intermittently after deployment.", result.optimized_prompt)
        self.assertIn("engineering team can follow tomorrow morning", result.optimized_prompt)
        self.assertNotIn("realy", result.optimized_prompt)
        self.assertNotIn("figgure", result.optimized_prompt)
        self.assertNotIn("enginering", result.optimized_prompt)
        self.assertNotIn("tommorow", result.optimized_prompt)

    def test_strips_blockquote_prefix_from_coding_objective(self) -> None:
        result = optimize_prompt(
            "> I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty.",
            "code",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(boost_level=1),
        )
        self.assertIn("Objective: Diagnose and fix a Python function that crashes on empty-list input.", result.optimized_prompt)
        self.assertNotIn("> I need", result.optimized_prompt)


if __name__ == "__main__":
    unittest.main()
