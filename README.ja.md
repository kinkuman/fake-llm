# fake-llm

[English README](README.md)

ローカルテスト用の小さな fake LLM サーバです。

Chat Completions 互換っぽい API 形状で LLM のふりをしますが、中身はローカルで動くルールベースのおもちゃです。OpenAI とは関係ありません。

## Quick Start

```bash
uv sync
uv run fake-llm chat
```

互換 API サーバを起動します。

```bash
uv run fake-llm serve --host 127.0.0.1 --port 8000
```

Chat Completions API のように呼び出せます。

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "fake-llm",
    "messages": [
      {"role": "user", "content": "こんにちは"}
    ]
  }'
```

互換クライアントから使う場合は、base URL を次に設定します。

```text
http://127.0.0.1:8000/v1
```

API key は任意の文字列で構いません。これはローカルのおもちゃサーバであり、本物の LLM ではありません。

## Endpoints

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

`stream: true` は簡易的な Server-Sent Events chunk で対応しています。

## Data

`src/fake_llm/data/` にある同梱辞書は、このプロジェクト用の小さなオリジナルサンプルです。直接編集することも、別のデータディレクトリを指定することもできます。

```bash
uv run fake-llm chat --data-dir ./my-data
uv run fake-llm serve --data-dir ./my-data
```

期待するファイルは次の通りです。

- `random.txt`: フォールバック返答を1行に1つ
- `pattern.tsv`: `regex<TAB>response|response`
- `template.tsv`: `keyword_count<TAB>{noun} を含むテンプレート`

## License

MIT.
