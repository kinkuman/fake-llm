import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fake_llm.bot import Dictionary, Emotion, FakeLLM, PatternRule, tokenize


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
            self.assertEqual(bot._select_responder(), "pattern")
        with patch("fake_llm.bot.random.random", return_value=0.95):
            self.assertEqual(bot._select_responder(), "random")

    def test_each_response_mode_returns_text(self):
        bot = FakeLLM(seed=1)
        bot.markov.learn(tokenize("りんごとみかんを食べる"))
        with patch.object(bot, "_select_responder", return_value="what"):
            self.assertEqual(bot._choose_response("こんにちは", []), "こんにちはってなに？")
        with patch.object(bot, "_select_responder", return_value="pattern"):
            self.assertIn(bot._choose_response("こんにちは", []), [
                "こんにちは。今日は何の話をしますか？",
                "どうも、こんにちは",
            ])
        with patch.object(bot, "_select_responder", return_value="template"):
            self.assertIn("りんご", bot._choose_response("りんご", tokenize("りんご")))
        with patch.object(bot, "_select_responder", return_value="markov"):
            self.assertTrue(bot._choose_response("みかん", tokenize("みかん")))
        with patch.object(bot, "_select_responder", return_value="random"):
            self.assertIn(bot._choose_response("こんにちは", []), bot.dictionary.random_responses)

    def test_markov_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            bot = FakeLLM(seed=1, state_file=state_file)
            bot.emotion.adjust(3)
            bot.dictionary.study("りんごとみかんを食べる", tokenize("りんごとみかんを食べる"))
            bot.markov.learn(tokenize("りんごとみかんを食べる"))
            bot.save()

            loaded = FakeLLM(seed=1, state_file=state_file)
            self.assertEqual(loaded.emotion.mood, 3)
            self.assertTrue(loaded.markov.table)
            self.assertTrue(loaded.markov.generate(keyword="りんご"))
            self.assertIn("りんごとみかんを食べる", loaded.dictionary.random_responses)
            self.assertTrue(loaded.dictionary.learned_patterns)
            self.assertIn("{noun}と{noun}を食べる", loaded.dictionary.templates[2])

    def test_pattern_mood_delta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "random.txt").write_text("fallback\n", encoding="utf-8")
            (data_dir / "template.tsv").write_text("1\t{noun}\n", encoding="utf-8")
            (data_dir / "pattern.tsv").write_text("好き\tいいですね\t2\n嫌い\tそうですか\t-3\n", encoding="utf-8")
            dictionary = Dictionary(data_dir)
            self.assertEqual(dictionary.patterns[0].mood_delta, 2)
            self.assertEqual(dictionary.patterns[1].mood_delta, -3)
            self.assertEqual(dictionary.patterns[0].responses[0], {"need": 0, "phrase": "いいですね"})

    def test_emotion_update_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "random.txt").write_text("fallback\n", encoding="utf-8")
            (data_dir / "template.tsv").write_text("1\t{noun}\n", encoding="utf-8")
            (data_dir / "pattern.tsv").write_text("好き\tいいですね\t2\n", encoding="utf-8")
            dictionary = Dictionary(data_dir)
            emotion = Emotion()
            emotion.update("好きです", dictionary.patterns)
            self.assertEqual(emotion.mood, 1.5)
            emotion.update("関係ない", dictionary.patterns)
            self.assertEqual(emotion.mood, 1.0)

    def test_pattern_response_mood_condition(self):
        rule = PatternRule("愛してる", "0##はいはい|2##まんざらでもないです|-2##今はそういう気分ではないです", 3)
        self.assertEqual(rule.choose_response(mood=0), "はいはい")
        self.assertIn(rule.choose_response(mood=3), ["はいはい", "まんざらでもないです"])
        self.assertIn(rule.choose_response(mood=-3), ["はいはい", "今はそういう気分ではないです"])

    def test_dictionary_study(self):
        bot = FakeLLM(seed=1)
        words = tokenize("りんごとみかんを食べる")
        bot.dictionary.study("りんごとみかんを食べる", words)
        self.assertIn("りんごとみかんを食べる", bot.dictionary.random_responses)
        self.assertTrue(bot.dictionary.learned_patterns)
        self.assertIn("{noun}と{noun}を食べる", bot.dictionary.templates[2])


if __name__ == "__main__":
    unittest.main()
