# システムプロンプト由来 pattern 返答 設計書

## 日付
2026/06/10

## 目的

GUI や互換 API クライアントから fake-llm を試すとき、TSV ファイルを編集せずに一時的な pattern 返答を指定できるようにする。

`pattern.tsv` は TAB 区切りのため、GUI の入力欄では編集しづらい。そこで、`role: system` の message content に書ける独自記法を追加し、リクエスト単位または CLI chat セッション単位の簡易制御として扱う。

## 基本方針

- system prompt に書かれた pattern ルールは一時ルールとして扱う。
- 一時ルールは `state.json` に保存しない。
- API サーバでは、一時ルールを次のリクエストへ持ち越さない。
- 同梱辞書や学習済み辞書は直接変更しない。
- デフォルトでは、既存の responder 抽選を維持する。
- オプション指定時だけ、system pattern 一致を responder 抽選より優先する。

## 対象

### 対応する入口

- `POST /v1/chat/completions`
  - `messages` 内の `role: system` を読む。
  - 強制優先はサーバ起動時の `--force-system-patterns` で受け取る。
- `fake-llm chat`
  - 動作確認用に `--system-prompt` と `--system-file` を追加する。
  - 動作確認用に `--force-system-patterns` を追加する。

### 対応しない入口

- `fake-llm serve` に `--system-prompt` や `--system-file` は追加しない。

API 利用時の system prompt はリクエスト側にある方が直感的である。サーバ起動時にも system prompt 相当の設定を持たせると、クライアントから見えない前提が増え、優先順位も分かりにくくなるため対象外とする。

ただし、強制優先の ON/OFF は API payload ではなくサーバ起動時の `--force-system-patterns` で指定する。GUI クライアントが任意の JSON 項目を送れない場合でも、サーバ側の起動オプションだけで挙動を切り替えられるようにするためである。

## 記法

system prompt 内で、次の形式の行を pattern ルールとして読む。

```text
pattern: 正規表現 => 返答1|返答2 mood=数値
```

例。

```text
pattern: ^ping$ => pong
pattern: こんにちは => やあ|こんにちは
pattern: バカ|ばか|馬鹿 => 乱暴な言葉は苦手です mood=-2
pattern: 愛してる => 0##はいはい|3##急に優しいですね mood=3
```

### 各要素

- `pattern:` は行頭に書く。
- `=>` の左側は Python の正規表現として扱う。
- `=>` の右側は返答候補として扱う。
- 返答候補は既存の `pattern.tsv` と同じく `|` で区切れる。
- 返答候補には既存の `need##phrase` 形式を使える。
- `mood=数値` は任意。
- `mood=数値` がない場合、`mood_delta` は `0` とする。
- 空行や `pattern:` で始まらない行は無視する。
- パースできない `pattern:` 行は無視し、返答処理全体は失敗させない。

## 優先度

### デフォルト動作

デフォルトでは、既存の responder 抽選を維持する。

```text
What / Pattern / Template / Markov / Random
```

抽選で Pattern responder が選ばれたときだけ、次の順で pattern を評価する。

1. system prompt 由来の一時 pattern
2. 同梱辞書と学習済み辞書の pattern

この動作では、system pattern に一致する入力でも、responder 抽選によって Random や What などが返ることがある。

### 強制優先動作

`--force-system-patterns` が有効な場合、system pattern に一致した時点で responder 抽選より前に返答する。

API サーバ起動例。

```bash
uv run fake-llm serve --host 127.0.0.1 --port 8000 --force-system-patterns
```

CLI 例。

```bash
uv run fake-llm chat --system-prompt 'pattern: ^ping$ => pong' --force-system-patterns
```

## 保存と学習

system prompt 由来の pattern は、`Dictionary.learned_patterns` に追加しない。

API サーバは `FakeLLM` インスタンスを使い回すため、一時 pattern を `self.dictionary.patterns` に直接追加しない。`reply()` の呼び出し中だけ使う一時リストとして扱う。

ユーザー発話そのものの通常学習は既存通り行う。

- random 返答への学習
- learned pattern への学習
- learned template への学習
- Markov 学習
- mood 保存

つまり、保存しない対象は system prompt 由来の pattern 定義だけである。

## 実装案

### bot.py

- system message を取り出す helper を追加する。
- system prompt の `pattern:` 行を `PatternRule` に変換する parser を追加する。
- `FakeLLM.reply()` に `force_system_patterns=False` を追加する。
- `FakeLLM.reply()` 内で一時 pattern を作る。
- `force_system_patterns=True` の場合は、学習前に system pattern の即時一致を試す。
- 通常 pattern responder では、一時 pattern を既存 pattern より先に評価する。
- `Emotion.update()` には、一時 pattern と既存 pattern を合わせたリストを渡す。

### api.py

- `serve()` と `make_handler()` に `force_system_patterns=False` を追加する。
- サーバ起動時の設定を `bot.reply(messages, force_system_patterns=...)` へ渡す。
- payload 独自項目では強制優先を指定しない。

### cli.py

- `fake-llm chat` に `--system-prompt` を追加する。
- `fake-llm chat` に `--system-file` を追加する。
- `fake-llm chat` に `--force-system-patterns` を追加する。
- CLI chat では、指定された system prompt を `messages` の先頭に入れて `reply()` へ渡す。

## テスト方針

- system pattern が通常 pattern より優先されること。
- デフォルトでは responder 抽選が Pattern の時だけ system pattern が使われること。
- `force_system_patterns=True` では responder 抽選より前に system pattern が使われること。
- system pattern が `state.json` に保存されないこと。
- API サーバ起動時相当の `force_system_patterns` が効くこと。
- CLI chat の `--system-prompt` と `--system-file` が system message として渡されること。
- 不正な `pattern:` 行があっても落ちないこと。

## ドキュメント更新

実装時には、少なくとも `README.ja.md` に次を追記する。

- system prompt pattern の記法。
- API payload 例。
- `--force-system-patterns` の意味。
- CLI chat の `--system-prompt` / `--system-file` / `--force-system-patterns`。
- API server の `--force-system-patterns`。
- system pattern は保存されないこと。

必要に応じて `README.md` にも同等の説明を追加する。

## 未決事項

現時点では大きな未決事項はない。

実装時に判断する細部は次の通り。

- 複数 system message はすべて連結して読む。
- `mood=数値` の位置は返答候補末尾のみ対応する。
- invalid regex は無視する。
- パース失敗時の warning は初回実装では出さない。
