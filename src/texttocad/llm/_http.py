"""Minimal JSON-over-HTTP helpers (stdlib only, no extra deps).

Kept tiny and dependency-free so the LLM subsystem imports cleanly in the test
environment. Tests monkeypatch ``post_json`` / ``get_json`` — no real network is used.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class HTTPError(RuntimeError):
    """Transport-level failure (connection refused, timeout, non-2xx)."""


def get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        # URL is an http(s) endpoint built from config, never user-supplied file/ftp schemes.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPError(f"GET {url} failed: {exc}") from exc


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        # URL is an http(s) endpoint built from config, never user-supplied file/ftp schemes.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPError(f"POST {url} failed: {exc}") from exc


def extract_json_object(text: str) -> dict:
    """Parse the first complete JSON object from ``text`` (tolerant of stray prose)."""
    text = text.strip()
    # Strip accidental markdown fences.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fall back to brace-matching for the first object.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in model output")
