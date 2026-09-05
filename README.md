# Nomic llama.cpp Prefix Adapter

A small compatibility layer for using asymmetric Nomic embedding models with
OpenAI-compatible clients and `llama-server`.

Nomic Embed Text (v1.5 and v2) expects different literal prefixes for search queries and
indexed documents:

```text
search_query: why did the backup fail?
search_document: The backup failed because the thin pool reached its threshold.
```

Some clients send that distinction as an `input_type` JSON field instead.
`llama-server` accepts the request but does not translate that field into a
prefix. This adapter performs that translation before forwarding the request.

## OpenClaw use case

This adapter is intended for an OpenClaw deployment that:

- keeps the official OpenClaw image instead of maintaining a custom fork;
- uses `memory.search.provider: openai-compatible`;
- sends embeddings to an external Nomic model served by `llama-server`; and
- configures `queryInputType` and `documentInputType` to distinguish searches
  from indexed memory chunks.

Stock OpenClaw sends those values as the OpenAI-compatible `input_type` field.
`llama-server` currently ignores that field, so the text reaches Nomic without
its asymmetric task prefix. Retrieval may still appear to work, but semantic
ranking is less reliable because queries and documents were not embedded using
the roles Nomic expects.

The adapter lets OpenClaw continue tracking official releases while fixing that
protocol mismatch outside the OpenClaw container. It is unnecessary when the
client already prepends literal Nomic prefixes or the embedding server natively
interprets `input_type`.

## Request flow

```text
OpenClaw or another OpenAI-compatible client
  -> prefix adapter :8081
  -> llama-server 127.0.0.1:8082
  -> Nomic embedding model
```

The adapter maps:

| `input_type` | Literal prefix |
|---|---|
| `search_query` | `search_query: ` |
| `search_document` | `search_document: ` |

Untyped, unprefixed requests are rejected instead of generating ambiguous
embeddings. Existing literal prefixes are preserved and never duplicated.

## Requirements

- Python 3.11 or newer; no third-party Python packages
- A recent `llama-server` build with embedding support
- A Nomic embedding GGUF model
- systemd for the supplied service units

This repository does not include model weights.

## Configuration

Copy the example environment file and set the interface that trusted clients
can reach:

```bash
sudo cp nomic-prefix-adapter.env.example /etc/default/nomic-prefix-adapter
sudo editor /etc/default/nomic-prefix-adapter
```

The safe default binds the adapter to loopback. A Tailscale deployment can set
`ADAPTER_BIND_HOST` to that machine's Tailscale address without committing the
address to Git.

## Included files

- `adapter.py` — HTTP adapter implemented with the Python standard library
- `nomic-prefix-adapter.service` — hardened systemd unit for the adapter
- `nomic-prefix-adapter.env.example` — deployment-specific network settings
- `llama-embedding.service` — example loopback-only `llama-server` unit
- `migrate-services.sh` — guarded service migration with automatic rollback
- `test_adapter.py` — prefix-handling unit tests
- `integration_check.py` — compares adapter output with manually prefixed output

## OpenClaw configuration

```json
{
  "memory": {
    "search": {
      "enabled": true,
      "provider": "openai-compatible",
      "model": "nomic-embed-text-v1.5",
      "remote": {
        "baseUrl": "http://<ADAPTER_ADDRESS>:8081/v1"
      },
      "queryInputType": "search_query",
      "documentInputType": "search_document"
    }
  }
}
```

Rebuild the memory index after changing embedding models. Do not mix vectors
created by different models or prefix strategies in the same index.

## Validation

Run the unit tests:

```bash
python3 -m unittest -v test_adapter.py
```

After both services are running, provide deployment-specific endpoints through
environment variables and run:

```bash
ADAPTER_EMBEDDINGS_URL=http://<ADAPTER_ADDRESS>:8081/v1/embeddings \
  python3 integration_check.py
```

A successful integration check reports exact vector matches for query and
document inputs.

## Security notes

- Bind `llama-server` to loopback so clients cannot bypass prefix enforcement.
- Bind the adapter only to a trusted interface or protect it with firewall rules.
- The adapter logs request metadata, never embedding input text.
- Keep deployment-specific addresses in `/etc/default/nomic-prefix-adapter`,
  outside the repository.
