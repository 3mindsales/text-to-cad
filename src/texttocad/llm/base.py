"""The LLM backend interface (SPEC 4.3) and shared error types.

The rest of the app depends ONLY on ``LLMBackend`` — never on a concrete provider.
Backends are selected by the router (``llm/router.py``) from config + hardware.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """Base class for LLM subsystem errors."""


class LLMUnavailableError(LLMError):
    """The backend (daemon/model/endpoint) is not reachable or ready."""


class ExternalProviderRefused(LLMError):
    """A non-local backend was requested without the required opt-in (SPEC 4.3/9.5)."""


class LLMBackend(ABC):
    """Abstract provider interface. See SPEC 4.3.

    ``generate_json`` must return a parsed dict (JSON/structured mode). ``is_local``
    is True only for air-gapped-safe backends; a True value is what keeps the app
    from opening external sockets (I4).
    """

    #: Human-readable provider name, e.g. "ollama", "anthropic".
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap readiness probe (daemon up, model present, endpoint reachable)."""

    @abstractmethod
    def generate_json(self, system: str, user: str, schema_hint: dict | None = None) -> dict:
        """Return a parsed JSON object from the model (JSON/structured output)."""

    @abstractmethod
    def generate_text(self, system: str, user: str) -> str:
        """Return raw text from the model."""

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """True => air-gapped-safe (offline model on localhost)."""

    def describe(self) -> str:
        """Short status string for logs / the status pill."""
        loc = "local" if self.is_local else "EXTERNAL"
        return f"{self.name} ({loc})"
