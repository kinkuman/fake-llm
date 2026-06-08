import unittest
from unittest.mock import patch

from fake_llm.bot import FakeLLM, tokenize


class BotTest(unittest.TestCase):
    def test_tokenize(self):
        self.assertIn("こんにちは", tokenize("こんにちは、AI"))
        self.assertIn("AI", tokenize("こんにちは、AI"))

    def test_reply_returns_text(self):
        bot = FakeLLM(seed=1)
        response = bot.reply([{"role": "user", "content": "こんにちは"}])
        self.assertTrue(response)
        self.assertIsInstance(response, str)

    def test_response_modes(self):
        bot = FakeLLM(seed=1)
        with patch("fake_llm.bot.random.random", return_value=0.1):
            self.assertIn(bot._choose_response("こんにちは", []), [
                "こんにちは。今日は何の話をしますか？",
                "どうも、こんにちは",
            ])
        with patch("fake_llm.bot.random.random", return_value=0.7):
            self.assertIn(bot._choose_response("こんにちは", []), bot.dictionary.random_responses)
        with patch("fake_llm.bot.random.random", return_value=0.95):
            self.assertEqual(bot._choose_response("こんにちは", []), "こんにちはってなに？")


if __name__ == "__main__":
    unittest.main()
