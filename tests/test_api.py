import unittest

from fake_llm.api import chat_completion_response, model_list_response
from fake_llm.bot import DEFAULT_MODEL, FakeLLM


class ApiTest(unittest.TestCase):
    def test_models_shape(self):
        payload = model_list_response()
        self.assertEqual(payload["object"], "list")
        self.assertEqual(payload["data"][0]["id"], DEFAULT_MODEL)

    def test_chat_completion_shape(self):
        bot = FakeLLM(seed=1)
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "こんにちは"}],
        }
        response = chat_completion_response(bot, payload)
        self.assertEqual(response["object"], "chat.completion")
        self.assertEqual(response["choices"][0]["message"]["role"], "assistant")
        self.assertTrue(response["choices"][0]["message"]["content"])
        self.assertIn("usage", response)


if __name__ == "__main__":
    unittest.main()
