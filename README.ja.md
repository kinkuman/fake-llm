# fake-llm

[English README](README.md)

ローカルテスト用の小さな fake LLM サーバです。

Chat Completions 互換っぽい API 形状で LLM のふりをしますが、中身はローカルで動くルールベースのおもちゃです。OpenAI とは関係ありません。

## Quick Start

```bash
uv sync
uv run fake-llm chat
```

fake-llm は日本語の分かち書きに Janome を使います。

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
- `pattern.tsv`: `regex<TAB>response|response<TAB>mood_delta`
- `template.tsv`: `keyword_count<TAB>{noun} を含むテンプレート`

`mood_delta` 列は任意です。正の値なら mood が良くなり、負の値なら悪くなります。mood は会話ごとに少しずつ中立へ戻ります。
mood の範囲は `-15` から `15` です。ユーザー発話ごとに `0.5` ずつ中立の `0` へ戻ります。

返答候補には任意で `need##phrase` を書けます。正の need は mood がその値より大きい時、負の need は mood がその値より小さい時に使われます。

```text
愛してる<TAB>0##はいはい|3##急に優しいですね<TAB>3
```

実用的な `need` の目安は `-10` から `10` くらいです。mood は `-15` 未満にも `15` 超えにもならず、現在の判定は厳密な比較なので、`-15##...` や `15##...` は実質ほぼ出ません。

## State

fake-llm は学習した Markov 状態を `state.json` に保存します。デフォルトでは現在の作業ディレクトリに作成します。`--data-dir` を指定した場合は、そのディレクトリ内に作成します。

`state.json` には、学習した random 返答、pattern ルール、template、mood も保存します。会話によって同梱辞書ファイルが直接書き換わることはありません。

保存先を明示することもできます。

```bash
uv run fake-llm chat --state-file ./state.json
uv run fake-llm serve --state-file ./state.json
```

## License

MIT.
