from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.optimizer import (
    PromptPreferences,
    _render_directive,
    _split_compound_action_line,
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

    def test_reasoning_lines_render_reasoning_section(self) -> None:
        result = _render_directive(
            goal="Build a launch plan.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
            reasoning_lines=["The goal is to onboard engineers faster."],
        )
        self.assertIn("Reasoning: The goal is to onboard engineers faster.", result)

    def test_reasoning_goal_preference_overrides_extracted_reasoning(self) -> None:
        result = _render_directive(
            goal="Build a launch plan.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(reasoning_goal="Speed matters most here."),
            mode="general",
            reasoning_lines=["The goal is something else."],
        )
        self.assertIn("Reasoning: Speed matters most here.", result)
        self.assertNotIn("something else", result)

    def test_stop_lines_render_stop_conditions_section(self) -> None:
        result = _render_directive(
            goal="Write a 30-day plan.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
            stop_lines=["Stop when there is one deliverable per week."],
        )
        self.assertIn("Stop-conditions:", result)
        self.assertIn("1. Stop when there is one deliverable per week.", result)

    def test_stop_conditions_preference_appended_to_stop_items(self) -> None:
        result = _render_directive(
            goal="Write a plan.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(stop_conditions="End with a summary table."),
            mode="general",
            stop_lines=["Stop when each week has an owner."],
        )
        self.assertIn("Stop-conditions:", result)
        self.assertIn("1. Stop when each week has an owner.", result)
        self.assertIn("2. End with a summary table.", result)

    def test_reasoning_and_stop_conditions_absent_when_not_set(self) -> None:
        result = _render_directive(
            goal="Explain recursion.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
        )
        self.assertNotIn("Reasoning:", result)
        self.assertNotIn("Stop-conditions:", result)

    def test_reasoning_appears_before_stop_conditions(self) -> None:
        result = _render_directive(
            goal="Build a plan.",
            context_lines=[],
            constraint_lines=[],
            output_lines=[],
            preferences=PromptPreferences(),
            mode="general",
            reasoning_lines=["The aim is to ship faster."],
            stop_lines=["Only stop when each sprint has a deliverable."],
        )
        reasoning_pos = result.index("Reasoning:")
        stop_pos = result.index("Stop-conditions:")
        self.assertLess(reasoning_pos, stop_pos)

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


class CompoundActionSplitTests(unittest.TestCase):
    def test_splits_four_parallel_action_clauses(self) -> None:
        line = "Analyze the likely root causes, prioritize the first diagnostic checks, recommend the most likely fix, and provide a clear step-by-step plan."
        parts = _split_compound_action_line(line)
        self.assertEqual(len(parts), 4)
        self.assertIn("Analyze the likely root causes.", parts)
        self.assertIn("Prioritize the first diagnostic checks.", parts)
        self.assertIn("Recommend the most likely fix.", parts)
        self.assertIn("Provide a clear step-by-step plan.", parts)

    def test_simple_single_clause_not_split(self) -> None:
        line = "Analyze the likely root causes of deployment failures."
        parts = _split_compound_action_line(line)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], line)

    def test_noun_list_not_split(self) -> None:
        # "validate" followed by only "," not "word word" — should not split
        line = "Create a function that can parse, validate, and transform data."
        parts = _split_compound_action_line(line)
        self.assertEqual(len(parts), 1)

    def test_two_clause_compound_split(self) -> None:
        line = "Explain the root cause, and recommend a concrete fix."
        parts = _split_compound_action_line(line)
        self.assertEqual(len(parts), 2)
        self.assertIn("Explain the root cause.", parts)
        self.assertIn("Recommend a concrete fix.", parts)

    def test_pipeline_prompt_produces_multiple_output_lines(self) -> None:
        result = optimize_prompt(
            "I need a strong prompt for claude to help me figure out why our python data pipeline keeps failing at random after we deploy. the logs are messy and sometimes it says timeout and other times memory error. I want claude to look at the possible root cause, tell me what to check first, suggest the most likely fix, and give me a clear step by step plan my engineering team can follow tomorrow morning.",
            "code",
            preferences=PromptPreferences(output_format="step-by-step", brevity="expert"),
        )
        self.assertIn("Task: Determine why our Python data pipeline keeps failing intermittently after deployment.", result.optimized_prompt)
        self.assertIn("Analyze the likely root causes.", result.optimized_prompt)
        self.assertIn("Prioritize the first diagnostic checks.", result.optimized_prompt)
        self.assertIn("Recommend the most likely fix.", result.optimized_prompt)
        self.assertIn("engineering team can follow tomorrow morning", result.optimized_prompt)
        # Should be multiple numbered rules
        self.assertIn("Rules:", result.optimized_prompt)
        self.assertIn("1.", result.optimized_prompt)
        self.assertIn("2.", result.optimized_prompt)
        self.assertIn("3.", result.optimized_prompt)


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


if __name__ == "__main__":
    unittest.main()
