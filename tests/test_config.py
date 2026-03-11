from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from promptopt.config import load_config, locate_config


class ConfigTests(unittest.TestCase):
    def test_locate_config_only_reads_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            config_path = root / ".promptopt.json"
            config_path.write_text("{}", encoding="utf-8")

            self.assertIsNone(locate_config(nested))

    def test_load_config_merges_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".promptopt.json").write_text(
                json.dumps(
                    {
                        "default_mode": "code",
                        "templates": {"general": "${persona_block}Task: $goal\n${length_block}"},
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(root)
            self.assertEqual(config.default_mode, "code")
            self.assertIn("$goal", config.templates["general"])
            self.assertIn("${instructions_block}", config.templates["code"])

    def test_invalid_mode_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".promptopt.json").write_text(
                json.dumps({"default_mode": "invalid"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(root)


if __name__ == "__main__":
    unittest.main()
