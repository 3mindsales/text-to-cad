"""Anthropic backend (Messages API, SPEC 4.4). Always non-local (I4).

Uses the Messages REST API directly (stdlib HTTP) so no SDK dependency is required.
The API key is read from env, never logged or persisted.
"""

from __future__ import annotations

import os

from texttocad.llm import _http
from texttocad.llm.base import LLMBackend, LLMUnavailableError

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicBackend(LLMBackend):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-5", api_key_env: str = "ANTHROPIC_API_KEY"):
        self.model = model
        self._api_key = os.environ.get(api_key_env)

    @property
    def is_local(self) -> bool:
        return False  # a hosted API is never air-gapped

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key or "",
            "anthropic-version": _API_VERSION,
        }

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _message(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            resp = _http.post_json(_API_URL, payload, headers=self._headers(), timeout=180)
        except _http.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        blocks = resp.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    def generate_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        guided = f"{user}\n\nReply with ONLY a single JSON object."
        return _http.extract_json_object(self._message(system, guided))

    def generate_text(self, system: str, user: str) -> str:
        return self._message(system, user)
