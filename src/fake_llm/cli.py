"""fake-llm のコマンドライン入口。

対話用の terminal chat とローカル互換 HTTP server を起動します。
`fake-llm` コマンドとして install される entry point です。
"""

import argparse
import json
from pathlib import Path

from . import __version__
from .api import serve
from .bot import (
    MAX_LEARNED_PATTERNS,
    MAX_LEARNED_RANDOM,
    MAX_LEARNED_TEMPLATES_PER_COUNT,
    MAX_MARKOV_PREFIXES,
    MAX_MARKOV_STARTS,
    FakeLLM,
    default_state_file,
)


def chat(data_dir=None, state_file=None):
    """簡単な terminal chat loop を開始する。"""
    bot = FakeLLM(data_dir=data_dir, state_file=state_file)
    print("Enter empty text to quit.")
    while True:
        text = input("you > ").rstrip()
        if not text:
            break
        response = bot.reply([{"role": "user", "content": text}])
        print("bot > " + response)
    bot.save()


def show_state(data_dir=None, state_file=None):
    """肥大化や学習状況を確認しやすいよう state.json の要約を表示する。"""
    path = resolve_state_file(data_dir, state_file)
    if not path.exists():
        print(f"state file not found: {path}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"failed to read state file: {error}")
        return 1

    dictionary = data.get("dictionary", {})
    markov = data.get("markov", {})
    templates = dictionary.get("templates", {})
    transitions = markov.get("table", [])

    print(f"path: {path}")
    print(f"version: {data.get('version', '-')}")
    print(f"mood: {data.get('mood', 0)}")
    print(f"learned random: {len(dictionary.get('random', []))}/{MAX_LEARNED_RANDOM}")
    print(f"learned patterns: {len(dictionary.get('patterns', []))}/{MAX_LEARNED_PATTERNS}")
    print(f"learned template groups: {len(templates)}")
    print(f"learned templates: {sum(len(value) for value in templates.values())}/{MAX_LEARNED_TEMPLATES_PER_COUNT} per group")
    print(f"markov starts: {len(markov.get('starts', []))}/{MAX_MARKOV_STARTS}")
    print(f"markov word pairs: {len(transitions)}/{MAX_MARKOV_PREFIXES}")
    return 0


def reset_state(data_dir=None, state_file=None):
    """検証をやり直しやすくするため state.json を空の初期状態へ戻す。"""
    path = resolve_state_file(data_dir, state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "mood": 0,
        "dictionary": {
            "random": [],
            "patterns": [],
            "templates": {},
        },
        "markov": {
            "starts": [],
            "table": [],
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reset state file: {path}")
    return 0


def resolve_state_file(data_dir=None, state_file=None):
    """CLI の指定方法が増えても state.json の決定規則を一箇所に保つ。"""
    if state_file:
        return Path(state_file)
    return default_state_file(data_dir)


def main(argv=None):
    """CLI 引数を parse して chat または server mode へ振り分ける。"""
    parser = argparse.ArgumentParser(prog="fake-llm")
    parser.add_argument("--version", action="version", version=f"fake-llm {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    chat_parser = subparsers.add_parser("chat", help="start a terminal chat")
    chat_parser.add_argument("--data-dir")
    chat_parser.add_argument("--state-file")

    serve_parser = subparsers.add_parser("serve", help="start the compatible HTTP API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--data-dir")
    serve_parser.add_argument("--state-file")
    serve_parser.add_argument("--quiet", action="store_true")

    state_parser = subparsers.add_parser("state", help="inspect or reset saved state")
    state_subparsers = state_parser.add_subparsers(dest="state_command")

    state_show_parser = state_subparsers.add_parser("show", help="show a state summary")
    state_show_parser.add_argument("--data-dir")
    state_show_parser.add_argument("--state-file")

    state_reset_parser = state_subparsers.add_parser("reset", help="reset saved state")
    state_reset_parser.add_argument("--data-dir")
    state_reset_parser.add_argument("--state-file")

    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(host=args.host, port=args.port, data_dir=args.data_dir, state_file=args.state_file, quiet=args.quiet)
    elif args.command == "state" and args.state_command == "show":
        return show_state(data_dir=args.data_dir, state_file=args.state_file)
    elif args.command == "state" and args.state_command == "reset":
        return reset_state(data_dir=args.data_dir, state_file=args.state_file)
    elif args.command == "state":
        state_parser.print_help()
        return 1
    else:
        chat(data_dir=getattr(args, "data_dir", None), state_file=getattr(args, "state_file", None))
    return 0
