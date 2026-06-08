import unittest

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


if __name__ == "__main__":
    unittest.main()
