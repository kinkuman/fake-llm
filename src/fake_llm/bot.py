"""fake-llm のルールベース会話エンジン。

このモジュールは、辞書の読み込み、パターン返答、テンプレート返答、
小さなオンメモリ Markov 学習、Chat Completions 風メッセージからの
テキスト抽出を担当します。
"""

import random
import re
from importlib import resources
from pathlib import Path


DEFAULT_MODEL = "fake-llm"


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
            pattern, responses = line.split("\t", 1)
            patterns.append((re.compile(pattern), [x for x in responses.split("|") if x]))
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


class FakeLLM:
    """単純なルールベース返答器で LLM のふりをする本体クラス。"""

    def __init__(self, data_dir=None, seed=None):
        """fake-llm の返答器を作る。

        Args:
            data_dir: 任意のカスタム辞書ディレクトリ。
            seed: テストで結果を固定したい時の乱数 seed。
        """
        self.dictionary = Dictionary(data_dir)
        self.markov = MarkovChain()
        self.history = []
        if seed is not None:
            random.seed(seed)

    def reply(self, messages):
        """Chat Completions 風メッセージに対して assistant 返答を1つ返す。"""
        user_text = latest_user_text(messages)
        if not user_text:
            return random.choice(self.dictionary.random_responses)
        words = tokenize(user_text)
        response = self._pattern_response(user_text)
        if response is None:
            response = self._template_response(words)
        if response is None and self.markov.table and random.random() < 0.35:
            response = self.markov.generate(keyword=last_keyword(words))
        if not response:
            response = random.choice(self.dictionary.random_responses)
        self.markov.learn(words)
        self.history.append((user_text, response))
        return response

    def _pattern_response(self, text):
        """最初に一致した正規表現ルールからランダムに返答を返す。"""
        for pattern, responses in self.dictionary.patterns:
            if pattern.search(text):
                return random.choice(responses)
        return None

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


def latest_user_text(messages):
    """メッセージ一覧から最後の user 発話テキストを取り出す。"""
    for message in reversed(messages or []):
        if message.get("role") == "user":
            return content_to_text(message.get("content", ""))
    return ""


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
    """日本語、英数字、記号を大まかなトークンに分割する。"""
    return re.findall(r"[A-Za-z0-9_]+|[ぁ-んァ-ン一-龥ー]+|[^\s]", text)


def keywords_from(words):
    """テンプレートや Markov の起点に使うキーワード候補を選ぶ。"""
    skip = {"これ", "それ", "あれ", "です", "ます", "する", "いる", "ある", "こと", "もの"}
    keywords = []
    for word in words:
        if word in skip:
            continue
        if re.search(r"[A-Za-z0-9ぁ-んァ-ン一-龥]", word) and len(word) >= 2:
            keywords.append(word)
    return keywords[:3]


def last_keyword(words):
    """トークン一覧から最後のキーワード候補を返す。"""
    keywords = keywords_from(words)
    return keywords[-1] if keywords else None
