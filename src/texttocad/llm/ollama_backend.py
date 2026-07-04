"""Ollama backend — serves BOTH offline-local models and Ollama Cloud (SPEC 4.1/4.4).

One adapter, two roles. ``is_local`` is computed at runtime (never hard-coded): it is
False if the model tag ends in ``-cloud`` OR the host is not localhost/private — which is
exactly what keeps a cloud call from masquerading as air-gapped (I4).
"""

from __future__ import annotations

import os

from texttocad.llm import _http
from texttocad.llm.base import LLMBackend, LLMUnavailableError
from texttocad.llm.locality import compute_is_local


class OllamaBackend(LLMBackend):
    name = "ollama"

    def __init__(self, host: str = "127.0.0.1:11434", model_tag: str = "qwen2.5-coder:7b-instruct"):
        self.host = host
        self.model_tag = model_tag
        # Cloud auth: read from env only; never logged, never persisted to config.
        self._api_key = os.environ.get("OLLAMA_API_KEY")

    # ------------------------------------------------------------------ #
    @property
    def is_local(self) -> bool:
        return compute_is_local(self.host, self.model_tag)

    def _base_url(self) -> str:
        host = self.host
        if "://" not in host:
            host = f"http://{host}"
        return host.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        try:
            tags = _http.get_json(f"{self._base_url()}/api/tags", headers=self._headers(), timeout=5)
        except _http.HTTPError:
            return False
        models = {m.get("name", "") for m in tags.get("models", [])}
        # Cloud tags may not appear in /api/tags; treat a reachable cloud host as available.
        return self.model_tag in models or not self.is_local

    def _chat(self, system: str, user: str, json_mode: bool) -> str:
        payload: dict = {
            "model": self.model_tag,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},  # determinism at the spec stage
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = _http.post_json(
                f"{self._base_url()}/api/chat", payload, headers=self._headers(), timeout=180
            )
        except _http.HTTPError as exc:
            raise LLMUnavailableError(str(exc)) from exc
        return str(resp.get("message", {}).get("content", ""))

    def generate_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        content = self._chat(system, user, json_mode=True)
        return _http.extract_json_object(content)

    def generate_text(self, system: str, user: str) -> str:
        return self._chat(system, user, json_mode=False)
