"""OpenAI-compatible backend (SPEC 4.4).

Covers OpenAI, LM Studio, vLLM, llama.cpp server, Groq, Together, OpenRouter, and
Ollama Cloud's ``/v1`` surface. ``is_local`` is True ONLY if ``base_url`` resolves to
localhost/private (I4). The API key is read from env, never logged or persisted.
"""

from __future__ import annotations

import os

from texttocad.llm import _http
from texttocad.llm.base import LLMBackend, LLMUnavailableError
from texttocad.llm.locality import is_local_host


class OpenAICompatibleBackend(LLMBackend):
    name = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key_env: str = "OPENAI_API_KEY"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = os.environ.get(api_key_env)

    @property
    def is_local(self) -> bool:
        return is_local_host(self.base_url)

    def _headers(self) -> dict[str, str]:
        h = {}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def is_available(self) -> bool:
        try:
            _http.get_json(f"{self.base_url}/models", headers=self._headers(), timeout=5)
            return True
        except _http.HTTPError:
            return False

    def _chat(self, system: str, user: str, json_mode: bool) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = _http.post_json(
                f"{self.base_url}/chat/completions", payload, headers=self._headers(), timeout=180
            )
        except _http.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        return str(resp["choices"][0]["message"]["content"])

    def generate_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        return _http.extract_json_object(self._chat(system, user, json_mode=True))

    def generate_text(self, system: str, user: str) -> str:
        return self._chat(system, user, json_mode=False)
