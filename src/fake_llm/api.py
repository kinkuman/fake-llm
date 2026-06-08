"""fake-llm の HTTP API 層。

このモジュールは Python 標準ライブラリだけで、Chat Completions 風 endpoint
のごく小さな一部を提供します。目的はローカル互換性テストであり、
本物の API を完全再現することではありません。
"""

import argparse
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .bot import DEFAULT_MODEL, FakeLLM


def chat_completion_response(bot, payload):
    """非 streaming の chat completion 返答 dict を作る。"""
    model = payload.get("model") or DEFAULT_MODEL
    messages = payload.get("messages") or []
    content = bot.reply(messages)
    created = int(time.time())
    prompt_tokens = estimate_tokens(json.dumps(messages, ensure_ascii=False))
    completion_tokens = estimate_tokens(content)
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def model_list_response():
    """fake-llm が公開する単一ローカルモデルの一覧を返す。"""
    return {
        "object": "list",
        "data": [
            {
                "id": DEFAULT_MODEL,
                "object": "model",
                "created": 0,
                "owned_by": "local",
            }
        ],
    }


def estimate_tokens(text):
    """API 形状を合わせるための雑な token 数を返す。"""
    return max(1, len(str(text)) // 4)


def make_handler(bot):
    """FakeLLM インスタンスに紐づいた HTTP handler を作る。"""
    class Handler(BaseHTTPRequestHandler):
        """fake-llm の小さな HTTP API を処理する handler。"""

        server_version = "FakeLLM/0.1"

        def log_message(self, format, *args):
            """quiet 指定時は request log を出さない。"""
            if getattr(self.server, "quiet", False):
                return
            super().log_message(format, *args)

        def do_GET(self):
            """health と model list endpoint を処理する。"""
            if self.path == "/health":
                self._send_json({"status": "ok"})
            elif self.path == "/v1/models":
                self._send_json(model_list_response())
            else:
                self._send_json({"error": {"message": "not found"}}, status=404)

        def do_POST(self):
            """chat completions endpoint を処理する。"""
            if self.path != "/v1/chat/completions":
                self._send_json({"error": {"message": "not found"}}, status=404)
                return
            payload = self._read_json()
            response = chat_completion_response(bot, payload)
            if payload.get("stream"):
                self._send_stream(response)
            else:
                self._send_json(response)

        def _read_json(self):
            """JSON request body を読み込んで parse する。"""
            size = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(size).decode("utf-8") if size else "{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}

        def _send_json(self, payload, status=200):
            """JSON response body を書き出す。"""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_stream(self, response):
            """簡易 Server-Sent Events 形式で chat completion stream を返す。"""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            base = {
                "id": response["id"],
                "object": "chat.completion.chunk",
                "created": response["created"],
                "model": response["model"],
            }
            self._write_sse(dict(base, choices=[{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]))
            content = response["choices"][0]["message"]["content"]
            for chunk in chunk_text(content):
                self._write_sse(dict(base, choices=[{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]))
            self._write_sse(dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}]))
            self.wfile.write(b"data: [DONE]\n\n")

        def _write_sse(self, payload):
            """SSE の data frame を1つ書き出す。"""
            line = "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

    return Handler


def chunk_text(text, size=8):
    """streaming 返答用に固定長のテキスト片を順に返す。"""
    for index in range(0, len(text), size):
        yield text[index:index + size]


def serve(host="127.0.0.1", port=8000, data_dir=None, quiet=False):
    """ローカル fake-llm HTTP server を起動して待ち受け続ける。"""
    bot = FakeLLM(data_dir=data_dir)
    server = ThreadingHTTPServer((host, port), make_handler(bot))
    server.quiet = quiet
    print(f"Serving on http://{host}:{port}")
    print("Compatible base URL: " + f"http://{host}:{port}/v1")
    server.serve_forever()


def main(argv=None):
    """単体 API server コマンドとして実行する。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port, data_dir=args.data_dir, quiet=args.quiet)
