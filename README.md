# fake-llm

A tiny fake LLM server for local testing.

It pretends to be an LLM through a small Chat Completions-compatible API shape,
but it is only a local rule-based toy. It is not affiliated with OpenAI.

## Quick Start

```bash
uv sync
uv run fake-llm chat
```

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
- `pattern.tsv`: `regex<TAB>response|response`
- `template.tsv`: `keyword_count<TAB>template with {noun}`

## License

MIT.
