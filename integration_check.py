#!/usr/bin/env python3
import json
import os
import urllib.request


def embed(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["data"]


adapter = os.environ.get(
    "ADAPTER_EMBEDDINGS_URL", "http://127.0.0.1:8081/v1/embeddings"
)
upstream = os.environ.get(
    "UPSTREAM_EMBEDDINGS_URL", "http://127.0.0.1:8082/v1/embeddings"
)
model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text-v1.5")

query_via_adapter = embed(
    adapter,
    {"model": model, "input": "backup failure", "input_type": "search_query"},
)[0]["embedding"]
query_manual = embed(
    upstream,
    {"model": model, "input": "search_query: backup failure"},
)[0]["embedding"]
documents_via_adapter = embed(
    adapter,
    {"model": model, "input": ["document one", "document two"], "input_type": "search_document"},
)
documents_manual = embed(
    upstream,
    {"model": model, "input": ["search_document: document one", "search_document: document two"]},
)

print(json.dumps({
    "query_exact_match": query_via_adapter == query_manual,
    "document_1_exact_match": documents_via_adapter[0]["embedding"] == documents_manual[0]["embedding"],
    "document_2_exact_match": documents_via_adapter[1]["embedding"] == documents_manual[1]["embedding"],
    "dimensions": len(query_via_adapter),
}))
