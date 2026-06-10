# fake-llm

[English README](README.md)

[開発者ブログ](https://blogger.kinkuman.net/2026/06/fake-llm.html "fake-llm: LLMのふりをする小さな人工無能サーバを作った")

ローカルテスト用の小さな fake LLM サーバです。

Chat Completions 互換っぽい API 形状で LLM のふりをしますが、中身はローカルで動くルールベースのおもちゃです。

現在のバージョン: `0.1.0`

## Quick Start

```bash
uv sync
uv run fake-llm --version
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

## System Prompt Patterns

`role: system` の message に、一時的な pattern 返答を書けます。これは `state.json` には保存されず、API サーバの次リクエストにも持ち越されません。

```text
pattern: 正規表現 => 返答1|返答2 mood=数値
```

例。

```json
{
  "model": "fake-llm",
  "messages": [
    {"role": "system", "content": "pattern: ^ping$ => pong"},
    {"role": "user", "content": "ping"}
  ]
}
```

デフォルトでは、通常の responder 抽選で pattern 返答が選ばれた時だけ system pattern を優先して使います。必ず system pattern を優先したい場合は、起動時に `--force-system-patterns` を指定します。

```bash
uv run fake-llm chat --system-prompt 'pattern: ^ping$ => pong' --force-system-patterns
uv run fake-llm chat --system-file ./system.txt
uv run fake-llm serve --host 127.0.0.1 --port 8000 --force-system-patterns
```

`serve` には system prompt 用オプションはありません。API 利用時はリクエストの `messages` に system message を入れてください。

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

`state.json` は長期記憶ではなく短期記憶として扱うため、保存数には上限があります。

- 学習 random 返答: 最新50件
- 学習 pattern ルール: 最新100件
- 学習 template: キーワード数ごとに最新30件
- Markov の開始候補: 最新200件
- Markov の prefix: 最新400件
- Markov の suffix: prefixごとに最新20件

保存先を明示することもできます。

```bash
uv run fake-llm chat --state-file ./state.json
uv run fake-llm serve --state-file ./state.json
```

保存された state の要約を確認できます。

```bash
uv run fake-llm state show --state-file ./state.json
```

保存された state を初期状態へ戻せます。

```bash
uv run fake-llm state reset --state-file ./state.json
```

## License

MIT.

利用時に作者名やリポジトリ名を紹介していただけると嬉しいです。
これは必須ではありません。