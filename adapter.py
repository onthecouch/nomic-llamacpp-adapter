#!/usr/bin/env python3
"""Translate OpenAI-compatible input_type metadata into Nomic text prefixes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


BIND_HOST = os.environ.get("ADAPTER_BIND_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("ADAPTER_BIND_PORT", "8081"))
UPSTREAM = os.environ.get("ADAPTER_UPSTREAM", "http://127.0.0.1:8082").rstrip("/")
MAX_BODY_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 60


def prefix_for_input_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().removesuffix(":")
    if normalized == "search_query":
        return "search_query: "
    if normalized == "search_document":
        return "search_document: "
    return None


def prefix_input(value: object, prefix: str | None) -> object:
    if isinstance(value, str):
        if value.startswith(("search_query: ", "search_document: ")):
            return value
        if prefix is None:
            raise ValueError("input_type must be search_query or search_document")
        return f"{prefix}{value}"
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [prefix_input(item, prefix) for item in value]
    raise ValueError("input must be a string or an array of strings")


class Handler(BaseHTTPRequestHandler):
    server_version = "nomic-prefix-adapter/1"

    def log_message(self, fmt: str, *args: object) -> None:
        # Log request metadata only. Never log embedded memory text.
        super().log_message(fmt, *args)

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy(self, method: str, path: str, body: bytes | None = None) -> None:
        request = urllib.request.Request(
            f"{UPSTREAM}{path}",
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                payload = response.read()
                self.send_bytes(
                    response.status,
                    payload,
                    response.headers.get("Content-Type", "application/json"),
                )
        except urllib.error.HTTPError as exc:
            self.send_bytes(
                exc.code,
                exc.read(),
                exc.headers.get("Content-Type", "application/json"),
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            payload = json.dumps({"error": {"message": f"embedding upstream unavailable: {exc.reason if hasattr(exc, 'reason') else exc}"}}).encode()
            self.send_bytes(502, payload, "application/json")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/v1/models"):
            self.proxy("GET", self.path)
            return
        self.send_bytes(404, b'{"error":{"message":"not found"}}', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/embeddings":
            self.send_bytes(404, b'{"error":{"message":"not found"}}', "application/json")
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_BODY_BYTES:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            prefix = prefix_for_input_type(payload.pop("input_type", None))
            payload["input"] = prefix_input(payload.get("input"), prefix)
        except (ValueError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": {"message": str(exc)}}).encode()
            self.send_bytes(400, body, "application/json")
            return
        self.proxy("POST", "/v1/embeddings", json.dumps(payload).encode())


if __name__ == "__main__":
    ThreadingHTTPServer((BIND_HOST, BIND_PORT), Handler).serve_forever()
