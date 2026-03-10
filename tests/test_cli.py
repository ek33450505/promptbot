from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.cli import (
    ask_numbered_choice,
    collect_advanced_preferences,
    collect_interactive_prompt,
    collect_preferences,
    main,
    read_prompt_text,
)
from promptopt.optimizer import PromptPreferences


class PromptReaderTests(unittest.TestCase):
    @patch("promptopt.cli.sys.stdin.isatty", return_value=True)
    def test_interactive_mode_returns_none(self, _mock_isatty) -> None:
        self.assertIsNone(read_prompt_text(()))

    @patch("promptopt.cli.sys.stdin.isatty", return_value=False)
    @patch("promptopt.cli.click.get_text_stream")
    def test_stdin_is_used_when_available(self, mock_stream, _mock_isatty) -> None:
        mock_stream.return_value.read.return_value = "Draft a summary."
        self.assertEqual(read_prompt_text(()), "Draft a summary.")


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_one_shot_prints_optimized_prompt(self) -> None:
        result = self.runner.invoke(main, ["Summarize this note"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Prompt to Copy", result.output)
        self.assertIn("Original Prompt", result.output)

    @patch("promptopt.cli.copy_to_clipboard")
    def test_one_shot_copy_copies_prompt(self, mock_copy) -> None:
        result = self.runner.invoke(main, ["--copy", "Summarize this note"])
        self.assertEqual(result.exit_code, 0)
        mock_copy.assert_called_once()
        self.assertIn("Copied to clipboard.", result.output)

    @patch("promptopt.cli.copy_to_clipboard")
    @patch("promptopt.cli.ask_numbered_choice", return_value="copy")
    @patch("promptopt.cli.collect_interactive_prompt", return_value="Please summarize this project.")
    @patch("promptopt.cli.collect_preferences", return_value=PromptPreferences(brevity="balanced"))
    @patch("promptopt.cli.read_prompt_text", return_value=None)
    def test_interactive_copy_flow(
        self,
        _mock_read,
        _mock_prefs,
        _mock_collect,
        _mock_ask,
        mock_copy,
    ) -> None:
        result = self.runner.invoke(main, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("promptbot", result.output)
        self.assertIn("The local-first prompt engineering toolkit", result.output)
        self.assertIn("production-ready LLM", result.output)
        self.assertIn("just better outputs", result.output)
        self.assertIn("local-first prompt engine online", result.output)
        self.assertIn("Original Prompt", result.output)
        self.assertIn("Copied to clipboard.", result.output)
        mock_copy.assert_called_once()

    @patch("promptopt.cli.console.input", side_effect=["Please rewrite this email.", ""])
    def test_collect_interactive_prompt(self, _mock_input) -> None:
        self.assertEqual(collect_interactive_prompt(), "Please rewrite this email.")

    @patch(
        "promptopt.cli.ask_numbered_choice",
        side_effect=["lean", "short paragraph"],
    )
    def test_collect_preferences(self, _mock_choice) -> None:
        preferences = collect_preferences()
        self.assertEqual(preferences.brevity, "lean")
        self.assertEqual(preferences.audience, "general")
        self.assertEqual(preferences.output_format, "short paragraph")
        self.assertEqual(preferences.persona, "")
        self.assertEqual(preferences.include, "")
        self.assertEqual(preferences.avoid, "")
        self.assertFalse(preferences.citations)
        self.assertFalse(preferences.reasoning)

    @patch(
        "promptopt.cli.ask_numbered_choice",
        side_effect=["balanced", "bullet points"],
    )
    def test_collect_preferences_uses_two_relevant_questions(self, _mock_choice) -> None:
        preferences = collect_preferences()
        self.assertEqual(preferences.brevity, "balanced")
        self.assertEqual(preferences.audience, "general")
        self.assertEqual(preferences.output_format, "bullet points")
        self.assertEqual(preferences.include, "")

    @patch("promptopt.cli.console.input", side_effect=["core example", "jargon"])
    @patch("promptopt.cli.ask_numbered_choice", return_value="advanced")
    def test_collect_advanced_preferences(self, _mock_choice, _mock_input) -> None:
        preferences = collect_advanced_preferences(PromptPreferences(brevity="balanced"))
        self.assertEqual(preferences.audience, "advanced")
        self.assertEqual(preferences.include, "core example")
        self.assertEqual(preferences.avoid, "jargon")
        self.assertEqual(preferences.boost_level, 0)

    @patch("promptopt.cli.ask_numbered_choice", side_effect=["strengthen", "quit"])
    @patch("promptopt.cli.collect_interactive_prompt", return_value="Please summarize this project.")
    @patch("promptopt.cli.collect_preferences", return_value=PromptPreferences(brevity="balanced"))
    @patch("promptopt.cli.read_prompt_text", return_value=None)
    @patch("promptopt.cli.optimize_prompt")
    def test_interactive_strengthen_reuses_same_prompt(
        self,
        mock_optimize,
        _mock_read,
        _mock_prefs,
        _mock_collect,
        _mock_ask,
    ) -> None:
        mock_optimize.side_effect = [
            type("Result", (), {"optimized_prompt": "first pass", "resolved_mode": "general"})(),
            type("Result", (), {"optimized_prompt": "second pass", "resolved_mode": "general"})(),
        ]
        result = self.runner.invoke(main, [])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(mock_optimize.call_count, 2)
        first_preferences = mock_optimize.call_args_list[0].kwargs["preferences"]
        second_preferences = mock_optimize.call_args_list[1].kwargs["preferences"]
        self.assertEqual(first_preferences.boost_level, 0)
        self.assertEqual(second_preferences.boost_level, 1)
        self.assertIn("Strength Pass: 1", result.output)

    @patch("promptopt.cli.ask_numbered_choice", return_value="quit")
    @patch("promptopt.cli.collect_interactive_prompt", side_effect=["/advanced", "Please summarize this project."])
    @patch("promptopt.cli.collect_advanced_preferences", return_value=PromptPreferences(brevity="balanced", audience="advanced"))
    @patch("promptopt.cli.collect_preferences", return_value=PromptPreferences(brevity="balanced"))
    @patch("promptopt.cli.read_prompt_text", return_value=None)
    def test_interactive_can_open_advanced_setup(
        self,
        _mock_read,
        _mock_prefs,
        mock_advanced,
        _mock_collect,
        _mock_ask,
    ) -> None:
        result = self.runner.invoke(main, [])
        self.assertEqual(result.exit_code, 0)
        mock_advanced.assert_called_once()
        self.assertIn("Prompt Entry", result.output)

    @patch("promptopt.cli.console.input", side_effect=["4", "expert"])
    def test_numbered_choice_supports_other(self, _mock_input) -> None:
        value = ask_numbered_choice(
            "Role",
            [
                ("concise", "short"),
                ("standard", "balanced"),
                ("extended", "detailed"),
            ],
            allow_other=True,
        )
        self.assertEqual(value, "expert")


if __name__ == "__main__":
    unittest.main()
