"""fake-llm のルールベース会話エンジン。

このモジュールは、辞書の読み込み、パターン返答、テンプレート返答、
小さなオンメモリ Markov 学習、Chat Completions 風メッセージからの
テキスト抽出を担当します。
"""

import random
import re
import json
from importlib import resources
from pathlib import Path

from janome.tokenizer import Tokenizer


DEFAULT_MODEL = "fake-llm"
TOKENIZER = Tokenizer()
KEYWORD_POS_DETAILS = {"一般", "固有名詞", "サ変接続", "形容動詞語幹"}


class Dictionary:
    """同梱データまたは指定ディレクトリから返答辞書を読み込むクラス。"""

    def __init__(self, data_dir=None):
        """全ての辞書テーブルを初期化する。

        Args:
            data_dir: random.txt、pattern.tsv、template.tsv を置いた任意の
                ディレクトリ。存在しないファイルは同梱データを使います。
        """
        self.data_dir = Path(data_dir) if data_dir else None
        self.random_responses = self._load_lines("random.txt")
        self.patterns = self._load_patterns("pattern.tsv")
        self.templates = self._load_templates("template.tsv")
        self.learned_random = []
        self.learned_patterns = []
        self.learned_templates = {}

    def _read_text(self, name):
        """指定辞書をカスタムデータ、同梱データの順に読み込む。"""
        if self.data_dir:
            path = self.data_dir / name
            if path.exists():
                return path.read_text(encoding="utf-8")
        return resources.files("fake_llm.data").joinpath(name).read_text(encoding="utf-8")

    def _load_lines(self, name):
        """通常テキストを空行なしの返答リストとして読み込む。"""
        lines = []
        for line in self._read_text(name).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        return lines or ["..."]

    def _load_patterns(self, name):
        """TSV から正規表現の返答ルールを読み込む。"""
        patterns = []
        for line in self._read_text(name).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            columns = line.split("\t")
            pattern = columns[0]
            responses = columns[1]
            mood_delta = int(columns[2]) if len(columns) >= 3 and columns[2] else 0
            patterns.append(PatternRule(pattern, responses, mood_delta))
        return patterns

    def _load_templates(self, name):
        """TSV からキーワード数別のテンプレートを読み込む。"""
        templates = {}
        for line in self._read_text(name).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            count_text, template = line.split("\t", 1)
            try:
                count = int(count_text)
            except ValueError:
                continue
            templates.setdefault(count, []).append(template)
        return templates

    def study(self, text, words):
        """ユーザー発話を random、pattern、template の学習候補に追加する。"""
        self.study_random(text)
        self.study_patterns(text, words)
        self.study_templates(words)

    def study_random(self, text):
        """発話全体を random 返答候補として覚える。"""
        if text and text not in self.random_responses:
            self.random_responses.append(text)
            if text not in self.learned_random:
                self.learned_random.append(text)

    def study_patterns(self, text, words):
        """キーワードごとに、同じ発話を pattern 返答候補として覚える。"""
        for keyword in keywords_from(words):
            rule = self.find_learned_pattern(keyword)
            if rule is None:
                rule = PatternRule(re.escape(keyword), text)
                self.patterns.append(rule)
                self.learned_patterns.append(rule)
            elif not rule.has_phrase(text):
                rule.responses.append({"need": 0, "phrase": text})

    def study_templates(self, words):
        """キーワードを {noun} に置き換えた template を覚える。"""
        keywords = keywords_from(words)
        if not keywords:
            return
        keyword_set = set(keywords)
        template = "".join("{noun}" if word in keyword_set else word for word in words)
        count = len(keywords)
        self.templates.setdefault(count, [])
        if template not in self.templates[count]:
            self.templates[count].append(template)
            self.learned_templates.setdefault(count, []).append(template)

    def find_learned_pattern(self, keyword):
        """学習済み pattern から keyword と同じ pattern の rule を探す。"""
        pattern = re.escape(keyword)
        for rule in self.learned_patterns:
            if rule.pattern_text == pattern:
                return rule
        return None

    def learned_to_dict(self):
        """学習済み辞書を JSON 保存できる dict に変換する。"""
        return {
            "random": self.learned_random,
            "patterns": [rule.to_dict() for rule in self.learned_patterns],
            "templates": {str(key): value for key, value in self.learned_templates.items()},
        }

    def load_learned(self, data):
        """state.json から学習済み辞書を読み込み、現在の辞書にマージする。"""
        for text in data.get("random", []):
            if text not in self.random_responses:
                self.random_responses.append(text)
            if text not in self.learned_random:
                self.learned_random.append(text)
        for item in data.get("patterns", []):
            rule = PatternRule.from_dict(item)
            self.patterns.append(rule)
            self.learned_patterns.append(rule)
        for count_text, templates in data.get("templates", {}).items():
            try:
                count = int(count_text)
            except ValueError:
                continue
            self.templates.setdefault(count, [])
            self.learned_templates.setdefault(count, [])
            for template in templates:
                if template not in self.templates[count]:
                    self.templates[count].append(template)
                if template not in self.learned_templates[count]:
                    self.learned_templates[count].append(template)


class PatternRule:
    """pattern.tsv の1行を表すルール。"""

    response_separator = re.compile(r"^((-?\d+(?:\.\d+)?)##)?(.*)$")

    def __init__(self, pattern, responses, mood_delta=0):
        """正規表現、返答候補、気分変化量を持つ。"""
        self.pattern_text = pattern
        self.pattern = re.compile(pattern)
        self.responses = [self._parse_response(x) for x in responses.split("|") if x]
        self.mood_delta = mood_delta

    def _parse_response(self, response):
        """need##phrase 形式の返答候補を解析する。"""
        match = self.response_separator.match(response)
        need = float(match.group(2)) if match and match.group(2) else 0
        phrase = match.group(3) if match else response
        return {"need": need, "phrase": phrase}

    def match(self, text):
        """入力に正規表現が一致すれば match object を返す。"""
        return self.pattern.search(text)

    def choose_response(self, mood=0):
        """mood 条件を満たす返答候補からランダムに1つ返す。"""
        choices = [response["phrase"] for response in self.responses if is_suitable(response["need"], mood)]
        return random.choice(choices) if choices else None

    def has_phrase(self, phrase):
        """同じ返答文を既に持っているか判定する。"""
        return any(response["phrase"] == phrase for response in self.responses)

    def to_dict(self):
        """JSON 保存できる dict に変換する。"""
        return {
            "pattern": self.pattern_text,
            "responses": self.responses,
            "mood_delta": self.mood_delta,
        }

    @classmethod
    def from_dict(cls, data):
        """保存済み dict から PatternRule を復元する。"""
        rule = cls(data.get("pattern", ""), "", data.get("mood_delta", 0))
        rule.responses = list(data.get("responses", []))
        return rule


def is_suitable(need, mood):
    """返答候補の mood 条件を満たしているか判定する。"""
    if need == 0:
        return True
    if need > 0:
        return mood > need
    return mood < need


class Emotion:
    """入力に応じて上下する小さな mood モデル。"""

    mood_min = -15
    mood_max = 15
    mood_recovery = 0.5

    def __init__(self):
        """mood 0 の状態で作る。"""
        self.mood = 0

    def clear(self):
        """mood を中立へ戻す。"""
        self.mood = 0

    def adjust(self, value):
        """mood を範囲内に収めながら増減する。"""
        self.mood += value
        self.mood = min(self.mood_max, max(self.mood_min, self.mood))

    def update(self, text, patterns):
        """一致した pattern の mood_delta を反映し、少し中立へ戻す。"""
        for rule in patterns:
            if rule.match(text):
                self.adjust(rule.mood_delta)
                break
        self.recover()

    def recover(self):
        """mood を少しずつ0へ戻す。"""
        if self.mood < 0:
            self.mood = min(0, self.mood + self.mood_recovery)
        elif self.mood > 0:
            self.mood = max(0, self.mood - self.mood_recovery)


class MarkovChain:
    """学習した断片から短文を作る小さなオンメモリ Markov 連鎖。"""

    end = "\0"

    def __init__(self):
        """空の連鎖テーブルを作る。"""
        self.table = {}
        self.starts = []

    def learn(self, words):
        """トークン化済みのユーザー発話から単語のつながりを学習する。"""
        words = [word for word in words if word]
        if len(words) < 3:
            return
        self.starts.append((words[0], words[1]))
        padded = words + [self.end]
        for index in range(len(padded) - 2):
            key = (padded[index], padded[index + 1])
            self.table.setdefault(key, []).append(padded[index + 2])

    def generate(self, keyword=None, max_words=30):
        """任意のキーワード付近から短い文章断片を生成する。"""
        if not self.table:
            return ""
        candidates = [key for key in self.table if keyword and keyword in key]
        if candidates:
            first, second = random.choice(candidates)
        elif self.starts:
            first, second = random.choice(self.starts)
        else:
            first, second = random.choice(list(self.table))
        words = [first, second]
        for _ in range(max_words):
            suffixes = self.table.get((first, second))
            if not suffixes:
                break
            suffix = random.choice(suffixes)
            if suffix == self.end:
                break
            words.append(suffix)
            first, second = second, suffix
        return "".join(words)

    def to_dict(self):
        """JSON 保存できる dict へ変換する。"""
        table = []
        for key, suffixes in self.table.items():
            table.append({
                "prefix": list(key),
                "suffixes": suffixes,
            })
        return {
            "starts": self.starts,
            "table": table,
        }

    @classmethod
    def from_dict(cls, data):
        """保存済み dict から MarkovChain を復元する。"""
        chain = cls()
        chain.starts = [tuple(item) for item in data.get("starts", [])]
        for item in data.get("table", []):
            prefix = item.get("prefix", [])
            if len(prefix) != 2:
                continue
            chain.table[(prefix[0], prefix[1])] = list(item.get("suffixes", []))
        return chain


class FakeLLM:
    """単純なルールベース返答器で LLM のふりをする本体クラス。"""

    responder_weights = {
        "what": 0.1,
        "pattern": 0.3,
        "template": 0.2,
        "markov": 0.2,
        "random": 0.2,
    }

    def __init__(self, data_dir=None, seed=None, state_file=None):
        """fake-llm の返答器を作る。

        Args:
            data_dir: 任意のカスタム辞書ディレクトリ。
            seed: テストで結果を固定したい時の乱数 seed。
            state_file: Markov 学習状態を保存・復元する JSON ファイル。
        """
        self.dictionary = Dictionary(data_dir)
        self.emotion = Emotion()
        self.markov = MarkovChain()
        self.history = []
        self.state_file = Path(state_file) if state_file else default_state_file(data_dir)
        self.load()
        if seed is not None:
            random.seed(seed)

    def reply(self, messages):
        """Chat Completions 風メッセージに対して assistant 返答を1つ返す。"""
        user_text = latest_user_text(messages)
        if not user_text:
            return random.choice(self.dictionary.random_responses)
        words = tokenize(user_text)
        self.emotion.update(user_text, self.dictionary.patterns)
        response = self._choose_response(user_text, words)
        self.dictionary.study(user_text, words)
        self.markov.learn(words)
        self.history.append((user_text, response))
        return response

    def _choose_response(self, text, words):
        """本家寄りに what、pattern、template、markov、random から返答を選ぶ。"""
        responder = self._select_responder()
        if responder == "what":
            return self._what_response(text)
        if responder == "pattern":
            return self._pattern_response(text) or self._random_response()
        if responder == "template":
            return self._template_response(words) or self._random_response()
        if responder == "markov":
            return self._markov_response(words) or self._random_response()
        return self._random_response()

    def _select_responder(self):
        """設定された重みに従って responder 名を1つ選ぶ。"""
        number = random.random()
        boundary = 0
        for name, weight in self.responder_weights.items():
            boundary += weight
            if number < boundary:
                return name
        return "random"

    def _pattern_response(self, text):
        """最初に一致した正規表現ルールからランダムに返答を返す。"""
        for rule in self.dictionary.patterns:
            match = rule.match(text)
            if match:
                response = rule.choose_response(self.emotion.mood)
                if response:
                    return response.replace("%match%", match.group(0))
        return None

    def _random_response(self):
        """random.txt からランダム返答を返す。"""
        return random.choice(self.dictionary.random_responses)

    def _what_response(self, text):
        """入力内容を聞き返す WhatResponder 風の返答を返す。"""
        return f"{text}ってなに？"

    def _markov_response(self, words):
        """Markov 連鎖で返答を作る。生成できない場合は None を返す。"""
        return self.markov.generate(keyword=last_keyword(words)) or None

    def _template_response(self, words):
        """キーワード数に合うテンプレートを埋めて返答を作る。"""
        keywords = keywords_from(words)
        templates = self.dictionary.templates.get(len(keywords))
        if not templates:
            return None
        template = random.choice(templates)
        for keyword in keywords:
            template = template.replace("{noun}", keyword, 1)
        return template

    def load(self):
        """state_file から Markov 学習状態を復元する。"""
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.emotion.mood = data.get("mood", 0)
        self.dictionary.load_learned(data.get("dictionary", {}))
        self.markov = MarkovChain.from_dict(data.get("markov", {}))

    def save(self):
        """state_file へ Markov 学習状態を保存する。"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "mood": self.emotion.mood,
            "dictionary": self.dictionary.learned_to_dict(),
            "markov": self.markov.to_dict(),
        }
        self.state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def latest_user_text(messages):
    """メッセージ一覧から最後の user 発話テキストを取り出す。"""
    for message in reversed(messages or []):
        if message.get("role") == "user":
            return content_to_text(message.get("content", ""))
    return ""


def default_state_file(data_dir=None):
    """data_dir 指定時はその中、それ以外はカレントの state.json を返す。"""
    if data_dir:
        return Path(data_dir) / "state.json"
    return Path("state.json")


def content_to_text(content):
    """文字列または list 形式の message content を通常テキストへ変換する。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def tokenize(text):
    """Janome で日本語文を単語単位に分割する。"""
    return [token.surface for token in TOKENIZER.tokenize(text)]


def keywords_from(words):
    """テンプレートや Markov の起点に使うキーワード候補を選ぶ。"""
    skip = {"これ", "それ", "あれ", "です", "ます", "する", "いる", "ある", "こと", "もの"}
    keywords = []
    text = "".join(words)
    for token in TOKENIZER.tokenize(text):
        word = token.surface
        if word in skip or word in {"？", "?", "！", "!"}:
            continue
        pos = token.part_of_speech.split(",")
        detail = pos[1] if len(pos) > 1 else ""
        if detail in KEYWORD_POS_DETAILS:
            keywords.append(word)
    return keywords[:3]


def last_keyword(words):
    """トークン一覧から最後のキーワード候補を返す。"""
    keywords = keywords_from(words)
    return keywords[-1] if keywords else None
