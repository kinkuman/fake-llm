"""CLI の補助コマンドが state.json を安全に扱えるか確認するテスト。"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from fake_llm.cli import reset_state, show_state


class CliTest(unittest.TestCase):
    def test_reset_and_show_state(self):
        """state reset 後に state show で空の状態を確認できる。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            reset_output = io.StringIO()
            with redirect_stdout(reset_output):
                reset_code = reset_state(state_file=state_file)

            output = io.StringIO()
            with redirect_stdout(output):
                show_code = show_state(state_file=state_file)

            self.assertEqual(reset_code, 0)
            self.assertEqual(show_code, 0)
            self.assertIn("mood: 0", output.getvalue())
            self.assertIn("learned random: 0/50", output.getvalue())
            self.assertIn("markov starts: 0/200", output.getvalue())

    def test_show_state_missing_file(self):
        """存在しない state を指定した時は失敗として扱う。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = io.StringIO()
            with redirect_stdout(output):
                code = show_state(state_file=Path(tmpdir) / "missing.json")

            self.assertEqual(code, 1)
            self.assertIn("state file not found", output.getvalue())


if __name__ == "__main__":
    unittest.main()
