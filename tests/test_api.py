"""Chat Completions 風 API response の形とサーバ設定を検証するテスト。"""

import unittest
from unittest.mock import patch

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

    def test_force_system_patterns_server_option(self):
        bot = FakeLLM(seed=1)
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": "pattern: ^ping$ => pong"},
                {"role": "user", "content": "ping"},
            ],
        }
        with patch.object(bot, "_select_responder", return_value="random"):
            response = chat_completion_response(bot, payload, force_system_patterns=True)
        self.assertEqual(response["choices"][0]["message"]["content"], "pong")


if __name__ == "__main__":
    unittest.main()
