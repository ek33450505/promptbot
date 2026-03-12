from __future__ import annotations

from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.claude_runner import ClaudeExecutionError, build_command, stream_claude
from promptopt.config import AppConfig


class FakePipe(StringIO):
    def __iter__(self):
        return iter(self.getvalue().splitlines(keepends=True))


class RecordingStdin(StringIO):
    def close(self) -> None:
        self.was_closed = True


class FakeProcess:
    def __init__(self) -> None:
        self.stdin = RecordingStdin()
        self.stdout = FakePipe("first line\nsecond line\n")
        self.killed = False

    def wait(self) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


class ClaudeRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig(
            claude_command="claude",
            default_model="",
            default_mode="auto",
            default_claude_args=("--permission-mode", "plan"),
            config_path=None,
        )

    def test_build_command_includes_model_and_extra_args(self) -> None:
        command = build_command(
            self.config,
            model_override="sonnet",
            extra_args=("--verbose",),
        )
        self.assertEqual(
            command,
            ["claude", "-p", "--model", "sonnet", "--permission-mode", "plan", "--verbose"],
        )

    @patch("promptopt.claude_runner.shutil.which", return_value="/Users/test/.local/bin/claude")
    @patch("promptopt.claude_runner.subprocess.Popen")
    def test_stream_claude_writes_prompt_and_streams_output(self, mock_popen, _mock_which) -> None:
        fake_process = FakeProcess()
        mock_popen.return_value = fake_process
        output = StringIO()

        exit_code = stream_claude(
            "Say hello",
            self.config,
            output_stream=output,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_process.stdin.getvalue(), "Say hello\n")
        self.assertIn("first line", output.getvalue())

    @patch("promptopt.claude_runner.shutil.which", return_value=None)
    def test_missing_binary_raises(self, _mock_which) -> None:
        with self.assertRaises(ClaudeExecutionError):
            stream_claude("Hello", self.config)


if __name__ == "__main__":
    unittest.main()
