"""CLI の補助コマンドと引数補助処理を検証するテスト。"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from fake_llm.cli import load_system_prompt, reset_state, show_state


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

    def test_load_system_prompt_combines_inline_and_file_text(self):
        """chat 入力欄にない system message を CLI 引数から再現できることを確認する。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            system_file = Path(tmpdir) / "system.txt"
            system_file.write_text("pattern: ^file$ => file response\n", encoding="utf-8")

            text = load_system_prompt(
                system_prompt="pattern: ^inline$ => inline response",
                system_file=system_file,
            )

        self.assertIn("pattern: ^inline$ => inline response", text)
        self.assertIn("pattern: ^file$ => file response", text)


if __name__ == "__main__":
    unittest.main()
