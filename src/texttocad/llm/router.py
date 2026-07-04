"""Backend router — tier selection + the hybrid routing / gating policy (SPEC 4.2).

Responsibilities:
- Resolve the model tier from config (or ``auto`` -> hardware probe).
- Construct the configured backend.
- ENFORCE gating: a non-local backend is refused unless ``allow_external_llm`` is set
  AND ``AIRGAP_STRICT`` is off (I4, SPEC 9.5). This is the single choke point the app
  relies on so a cloud/external call can never run un-opted-in.
- Decide whether Freeform is allowed (forced off on the 3b tier) and route Freeform to a
  cloud "Boost" when explicitly enabled.
"""

from __future__ import annotations

from texttocad import config
from texttocad.config import HardwareInfo, Settings
from texttocad.llm.base import ExternalProviderRefused, LLMBackend
from texttocad.llm.ollama_backend import OllamaBackend


def resolve_tier(settings: Settings, hardware: HardwareInfo) -> str:
    """Return the effective tier id, honouring an ``auto`` setting."""
    tier = settings.active_model_tier
    if tier == "auto":
        return hardware.recommended_tier
    if tier not in config.MODEL_TIERS:
        return hardware.recommended_tier
    return tier


def tier_tag(tier: str) -> str:
    return str(config.MODEL_TIERS[tier]["tag"])


def enforce_gating(backend: LLMBackend, settings: Settings) -> None:
    """Raise ExternalProviderRefused if a non-local backend is not opted-in (I4)."""
    if backend.is_local:
        return
    if settings.airgap_strict:
        raise ExternalProviderRefused("external/cloud LLM is disabled in an AIRGAP_STRICT build")
    if not settings.allow_external_llm:
        raise ExternalProviderRefused(
            "external/cloud LLM requires 'Allow external LLM providers' to be enabled"
        )


def _construct(settings: Settings, hardware: HardwareInfo) -> LLMBackend:
    tier = resolve_tier(settings, hardware)
    tag = tier_tag(tier)
    backend = settings.active_backend
    if backend == "ollama":
        return OllamaBackend(host=settings.ollama_host, model_tag=tag)
    if backend == "llamacpp":
        from texttocad.llm.llamacpp_backend import LlamaCppBackend

        return LlamaCppBackend(model_path=tag)  # tag doubles as a gguf path in this mode
    if backend == "openai_compat":
        from texttocad.llm.openai_compat_backend import OpenAICompatibleBackend

        return OpenAICompatibleBackend(base_url=settings.ollama_host, model=tag)
    if backend == "anthropic":
        from texttocad.llm.anthropic_backend import AnthropicBackend

        return AnthropicBackend()
    raise ValueError(f"unknown backend '{backend}'")


def build_backend(settings: Settings, hardware: HardwareInfo) -> LLMBackend:
    """Construct the primary backend and enforce gating before returning it."""
    backend = _construct(settings, hardware)
    enforce_gating(backend, settings)
    return backend


def freeform_allowed(settings: Settings, hardware: HardwareInfo) -> bool:
    """Freeform is off on the 3b tier and whenever the user hasn't enabled it (SPEC 4.2)."""
    if not settings.freeform_enabled:
        return False
    return resolve_tier(settings, hardware) != "3b"


def cloud_boost_backend(settings: Settings, cloud_tag: str = "qwen3-coder:480b-cloud") -> LLMBackend:
    """Build the Ollama Cloud 'Boost' backend for Freeform/complex calls, gated.

    The ``-cloud`` tag forces ``is_local == False``, so ``enforce_gating`` refuses it
    unless the external opt-in is set and AIRGAP_STRICT is off.
    """
    backend = OllamaBackend(host=settings.ollama_host, model_tag=cloud_tag)
    enforce_gating(backend, settings)
    return backend


def route(
    settings: Settings,
    hardware: HardwareInfo,
    call_kind: str,
    *,
    boost: bool = False,
) -> LLMBackend:
    """Pick a backend per call. Template stays local; Freeform may Boost to cloud.

    ``call_kind`` is "template" or "freeform". ``boost`` opts a Freeform call into the
    cloud tier (still gated). All returned backends have passed ``enforce_gating``.
    """
    if call_kind == "freeform" and boost:
        return cloud_boost_backend(settings)
    return build_backend(settings, hardware)
