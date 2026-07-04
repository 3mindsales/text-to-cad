"""Router tier selection + external/cloud gating (SPEC 4.2, I4)."""

from __future__ import annotations

import pytest

from texttocad.config import HardwareInfo, Settings
from texttocad.llm import router
from texttocad.llm.base import ExternalProviderRefused


def _hw(tier="7b"):
    return HardwareInfo(total_ram_gb=8.0, vram_gb=None, has_nvidia_gpu=False, recommended_tier=tier)


def test_resolve_tier_explicit_and_auto():
    assert router.resolve_tier(Settings(active_model_tier="14b"), _hw()) == "14b"
    assert router.resolve_tier(Settings(active_model_tier="auto"), _hw("3b")) == "3b"
    # Unknown tier falls back to the hardware recommendation.
    assert router.resolve_tier(Settings(active_model_tier="nope"), _hw("7b")) == "7b"


def test_build_default_backend_is_local():
    backend = router.build_backend(Settings(), _hw())
    assert backend.name == "ollama"
    assert backend.is_local is True


def test_external_refused_without_optin():
    s = Settings(active_backend="anthropic", allow_external_llm=False)
    with pytest.raises(ExternalProviderRefused):
        router.build_backend(s, _hw())


def test_external_allowed_with_optin():
    s = Settings(active_backend="anthropic", allow_external_llm=True, airgap_strict=False)
    backend = router.build_backend(s, _hw())
    assert backend.is_local is False


def test_airgap_strict_blocks_even_with_optin():
    # airgap_strict forces allow_external_llm off at load; simulate the runtime guard too.
    s = Settings(active_backend="anthropic", allow_external_llm=True, airgap_strict=True)
    with pytest.raises(ExternalProviderRefused):
        router.build_backend(s, _hw())


def test_cloud_boost_gated():
    # Cloud tag => non-local => refused without opt-in.
    with pytest.raises(ExternalProviderRefused):
        router.cloud_boost_backend(Settings(allow_external_llm=False))
    # Opted-in, non-strict => allowed and correctly classified non-local.
    b = router.cloud_boost_backend(Settings(allow_external_llm=True, airgap_strict=False))
    assert b.is_local is False


def test_freeform_forced_off_on_3b():
    # Effective tier comes from the active setting (or 'auto' -> hardware).
    assert router.freeform_allowed(Settings(active_model_tier="3b", freeform_enabled=True), _hw()) is False
    assert (
        router.freeform_allowed(Settings(active_model_tier="auto", freeform_enabled=True), _hw("3b")) is False
    )
    assert router.freeform_allowed(Settings(active_model_tier="7b", freeform_enabled=True), _hw()) is True
    assert router.freeform_allowed(Settings(freeform_enabled=False), _hw()) is False


def test_route_template_stays_local():
    b = router.route(Settings(), _hw(), "template")
    assert b.is_local is True
