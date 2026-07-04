"""In-process GGUF fallback via llama-cpp-python (SPEC 4.1). Always local (I4).

Used when Ollama cannot start (locked-down machine, no service rights). The heavy
``llama_cpp`` import is lazy so the module imports cleanly without the optional dep.
"""

from __future__ import annotations

from typing import Any

from texttocad.llm import _http
from texttocad.llm.base import LLMBackend, LLMUnavailableError


class LlamaCppBackend(LLMBackend):
    name = "llamacpp"

    def __init__(self, model_path: str, n_ctx: int = 4096):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self._llm: Any = None

    @property
    def is_local(self) -> bool:
        return True  # in-process GGUF never touches the network

    def _ensure(self) -> Any:
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - optional dep
                raise LLMUnavailableError("llama-cpp-python is not installed") from exc
            self._llm = Llama(model_path=self.model_path, n_ctx=self.n_ctx, verbose=False)
        return self._llm

    def is_available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        import os

        return os.path.exists(self.model_path)

    def _complete(self, system: str, user: str, json_mode: bool) -> str:
        llm = self._ensure()
        kwargs: dict[str, Any] = {"temperature": 0.0}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
        return str(out["choices"][0]["message"]["content"])

    def generate_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        return _http.extract_json_object(self._complete(system, user, json_mode=True))

    def generate_text(self, system: str, user: str) -> str:
        return self._complete(system, user, json_mode=False)
