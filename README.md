# fake-llm

[日本語 README](README.ja.md)

[developer blog](https://blogger.kinkuman.net/2026/06/fake-llm.html "fake-llm: LLMのふりをする小さな人工無能サーバを作った")

A tiny fake LLM server for local testing.

It pretends to be an LLM through a small Chat Completions-compatible API shape,
but it is only a local rule-based toy.

Current version: `0.1.0`

## Quick Start

```bash
uv sync
uv run fake-llm --version
uv run fake-llm chat
```

fake-llm uses Janome for Japanese tokenization.

Start the compatible toy server:

```bash
uv run fake-llm serve --host 127.0.0.1 --port 8000
```

Then call it like a Chat Completions API:

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

For compatible clients, set the base URL to:

```text
http://127.0.0.1:8000/v1
```

Any API key string is accepted. This is a local toy server, not an LLM.

## Endpoints

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

`stream: true` is supported with simple Server-Sent Events chunks.

## Data

The bundled dictionaries under `src/fake_llm/data/` are original small
sample files for this project. You can edit them or pass your own data
directory:

```bash
uv run fake-llm chat --data-dir ./my-data
uv run fake-llm serve --data-dir ./my-data
```

Expected files:

- `random.txt`: one fallback response per line
- `pattern.tsv`: `regex<TAB>response|response<TAB>mood_delta`
- `template.tsv`: `keyword_count<TAB>template with {noun}`

The `mood_delta` column is optional. Positive values make the bot mood better,
negative values make it worse, and the mood slowly returns to neutral.
Mood is clamped between `-15` and `15`, and moves `0.5` back toward neutral
after each user message.

Each response can optionally use `need##phrase`. A positive need is available
when mood is greater than that value, and a negative need is available when mood
is lower than that value.

```text
愛してる<TAB>0##はいはい|3##急に優しいですね<TAB>3
```

Practical `need` values are usually around `-10` to `10`. Since mood never goes
below `-15` or above `15`, conditions such as `-15##...` or `15##...` are
effectively unreachable with the current strict comparison.

## State

fake-llm saves learned Markov state to `state.json`. By default, the file is
created in the current working directory. When `--data-dir` is specified, it is
created inside that directory.

The state file also stores learned random responses, learned pattern rules,
learned templates, and mood. Bundled dictionary files are not modified by
conversation.

The state file is treated as short-term memory, not as a long-term knowledge
base, so learned entries are capped:

- Learned random responses: latest 50 entries
- Learned pattern rules: latest 100 entries
- Learned templates: latest 30 entries per keyword count
- Markov starts: latest 200 entries
- Markov prefixes: latest 400 entries
- Markov suffixes: latest 20 entries per prefix

You can also choose the state file explicitly:

```bash
uv run fake-llm chat --state-file ./state.json
uv run fake-llm serve --state-file ./state.json
```

Inspect the saved state:

```bash
uv run fake-llm state show --state-file ./state.json
```

Reset the saved state:

```bash
uv run fake-llm state reset --state-file ./state.json
```

## License

MIT.
