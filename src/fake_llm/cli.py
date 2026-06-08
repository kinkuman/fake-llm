"""fake-llm のコマンドライン入口。

対話用の terminal chat とローカル互換 HTTP server を起動します。
`fake-llm` コマンドとして install される entry point です。
"""

import argparse

from .api import serve
from .bot import FakeLLM


def chat(data_dir=None):
    """簡単な terminal chat loop を開始する。"""
    bot = FakeLLM(data_dir=data_dir)
    print("Enter empty text to quit.")
    while True:
        text = input("you > ").rstrip()
        if not text:
            break
        response = bot.reply([{"role": "user", "content": text}])
        print("bot > " + response)


def main(argv=None):
    """CLI 引数を parse して chat または server mode へ振り分ける。"""
    parser = argparse.ArgumentParser(prog="fake-llm")
    subparsers = parser.add_subparsers(dest="command")

    chat_parser = subparsers.add_parser("chat", help="start a terminal chat")
    chat_parser.add_argument("--data-dir")

    serve_parser = subparsers.add_parser("serve", help="start the compatible HTTP API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--data-dir")
    serve_parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(host=args.host, port=args.port, data_dir=args.data_dir, quiet=args.quiet)
    else:
        chat(data_dir=getattr(args, "data_dir", None))
