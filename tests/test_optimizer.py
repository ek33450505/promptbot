from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.optimizer import (
    PromptPreferences,
    _render_directive,
    detect_mode,
    normalize_prompt,
    optimize_prompt,
)


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

    def test_normalizes_common_debugging_phrases(self) -> None:
        prompt = "our python worker keeps crashing after deploy and sometimes its a timeout and other times memory spikes"
        normalized = normalize_prompt(prompt)
        self.assertIn("after deployment", normalized)
        self.assertIn("the logs alternate between timeouts and memory spikes", normalized)

    def test_normalizes_timeout_and_exception_context(self) -> None:
        prompt = "the logs are messy and sometimes its a timeout and other times ValueError"
        normalized = normalize_prompt(prompt)
        self.assertIn("the logs are messy, and failures alternate between timeouts and ValueError", normalized)


class DetectModeTests(unittest.TestCase):
    def test_detects_code_prompt_from_stack_trace(self) -> None:
        prompt = "Traceback (most recent call last):\nValueError: boom"
        self.assertEqual(detect_mode(prompt), "code")

    def test_detects_code_prompt_from_exception_name(self) -> None:
        prompt = "Debug this Python worker. It fails with ValueError when the queue is empty."
        self.assertEqual(detect_mode(prompt), "code")

    def test_detects_general_prompt(self) -> None:
        prompt = "Write a concise thank-you note for a colleague."
        self.assertEqual(detect_mode(prompt), "general")

    def test_does_not_match_repo_inside_report(self) -> None:
        prompt = "Make this bug report clearer."
        self.assertEqual(detect_mode(prompt), "general")


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


class OptimizePromptTests(unittest.TestCase):
    def test_auto_mode_uses_code_template(self) -> None:
        result = optimize_prompt(
            "Refactor src/app.py and add tests for the failure path.",
            "auto",
            DEFAULT_TEMPLATES,
        )
        self.assertEqual(result.resolved_mode, "code")
        self.assertIn("<task>", result.optimized_prompt)
        self.assertIn("<instructions>", result.optimized_prompt)
        self.assertIn("Clear, technically grounded, and implementation-focused.", result.optimized_prompt)
        self.assertIn("Prefer a general-purpose fix", result.optimized_prompt)
        self.assertNotIn("<role>", result.optimized_prompt)

    def test_general_mode_uses_general_template(self) -> None:
        result = optimize_prompt(
            "Summarize this meeting transcript in three bullets.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertEqual(result.resolved_mode, "general")
        self.assertIn("<style>", result.optimized_prompt)
        self.assertIn("Clear, direct, and moderately detailed.", result.optimized_prompt)

    def test_collects_multiple_output_lines(self) -> None:
        result = optimize_prompt(
            "Build a small CLI.\nReturn JSON.\nOutput a table to stdout.\nKeep it concise.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("<deliverables>", result.optimized_prompt)
        self.assertIn("- Return JSON.", result.optimized_prompt)
        self.assertIn("- Output a table to stdout.", result.optimized_prompt)
        self.assertIn("<constraints>", result.optimized_prompt)

    def test_removes_leading_filler_phrases(self) -> None:
        result = optimize_prompt(
            "Please help me summarize this project.",
            "general",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("<task>\nProvide a concise summary of this project.\n</task>", result.optimized_prompt)

    def test_rewrites_meta_prompt_language_into_direct_request(self) -> None:
        result = optimize_prompt(
            "I need a strong prompt for Claude to debug a Python function that crashes when the input list is empty. I want the answer to explain the root cause, show the fix, and include a small test case that proves the fix works.",
            "code",
            DEFAULT_TEMPLATES,
        )
        self.assertIn("<task>\nDiagnose and fix a Python function that crashes on empty-list input.\n</task>", result.optimized_prompt)
        self.assertIn("<deliverables>", result.optimized_prompt)
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
        self.assertIn("You are an expert biology teacher.", result.optimized_prompt)
        self.assertIn("<audience>\n  beginner\n</audience>", result.optimized_prompt)
        self.assertIn("Use this output format: 3 bullet points.", result.optimized_prompt)
        self.assertIn("<deliverables>", result.optimized_prompt)
        self.assertIn("Must include light-dependent reactions.", result.optimized_prompt)
        self.assertIn("<constraints>", result.optimized_prompt)
        self.assertIn("Exclude history.", result.optimized_prompt)
        self.assertIn("<quality_bar>", result.optimized_prompt)
        self.assertIn("<source_handling>", result.optimized_prompt)
        self.assertIn("<reasoning>", result.optimized_prompt)

    def test_infers_beginner_audience_from_prompt(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis to a middle school student.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("<audience>\n  beginner\n</audience>", result.optimized_prompt)

    def test_adds_step_by_step_guidance_for_code_prompts(self) -> None:
        result = optimize_prompt(
            "Debug a Python function that crashes when the input list is empty.",
            "code",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="step-by-step"),
        )
        self.assertIn("<task>\nDiagnose and fix a Python function that crashes on empty-list input.\n</task>", result.optimized_prompt)
        self.assertIn("Use numbered steps, isolate the root cause, show the fix, and end with a verification step.", result.optimized_prompt)

    def test_strengthen_pass_upgrades_goal_tone(self) -> None:
        result = optimize_prompt(
            "Explain photosynthesis.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(boost_level=1),
        )
        self.assertIn("<task>\nDeliver a precise explanation of photosynthesis.\n</task>", result.optimized_prompt)
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
        self.assertIn("<task>\nDetermine why our Python data pipeline keeps failing intermittently after deployment.\n</task>", result.optimized_prompt)
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
        self.assertIn("<task>\nDiagnose and fix a Python function that crashes on empty-list input.\n</task>", result.optimized_prompt)
        self.assertNotIn("> I need", result.optimized_prompt)

    def test_quality_feedback_becomes_clean_goal_and_output(self) -> None:
        result = optimize_prompt(
            "The prompts that are being returned with the new formatting are really not very clean - how can we ensure correct grammer and formatting. We seem to be including random sentences from the inital prompt.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("<task>\nEnsure correct grammar and formatting.\n</task>", result.optimized_prompt)
        self.assertIn("Prevent unrelated source sentences from leaking into the final prompt.", result.optimized_prompt)
        self.assertNotIn("grammer", result.optimized_prompt)
        self.assertNotIn("inital", result.optimized_prompt)
        self.assertNotIn("not very clean", result.optimized_prompt)

    def test_selects_actionable_line_instead_of_admin_context(self) -> None:
        result = optimize_prompt(
            "One last request before we push one last time. On the options sections we have a default number set adjacent to the Select [] :. Lets go ahead and get rid of the suggested option here. Additionally, On the Prompt to copy can we add some colors and styling here. Everything is jumbled together and its hard to read.",
            "general",
            DEFAULT_TEMPLATES,
            preferences=PromptPreferences(output_format="bullet points"),
        )
        self.assertIn("<task>\nRemove the suggested option.\n</task>", result.optimized_prompt)
        self.assertIn("<deliverables>\n    - Add some colors and styling to the prompt-to-copy panel.\n    - Improve readability and visual separation.\n  </deliverables>", result.optimized_prompt)
        self.assertIn("<context>\n  The selection prompt currently shows a suggested default number.\n</context>", result.optimized_prompt)
        self.assertNotIn("One last request before we push", result.optimized_prompt)


if __name__ == "__main__":
    unittest.main()
