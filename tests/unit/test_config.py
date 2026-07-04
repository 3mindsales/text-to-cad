"""Tests for the config module and first-run hardware probe (SPEC 4.2)."""

from __future__ import annotations

import os
from pathlib import Path

from texttocad import config


def test_recommend_tier_by_ram():
    assert config.recommend_tier(4.0, None) == "3b"
    assert config.recommend_tier(8.0, None) == "7b"
    assert config.recommend_tier(16.0, None) == "14b"
    assert config.recommend_tier(64.0, None) == "32b"


def test_recommend_tier_gpu_boost():
    # A 12 GB GPU (x1.5 = 18) should beat 8 GB system RAM and reach the 14b tier.
    assert config.recommend_tier(8.0, 12.0) == "14b"


def test_probe_hardware_shape():
    hw = config.probe_hardware()
    assert hw.total_ram_gb >= 0
    assert hw.recommended_tier in config.MODEL_TIERS
    assert isinstance(hw.has_nvidia_gpu, bool)


def test_settings_env_overrides(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TEXTTOCAD_CONFIG", str(tmp_path / "cfg.json"))
    monkeypatch.setenv("TEXTTOCAD_MODEL_TIER", "3b")
    monkeypatch.setenv("AIRGAP_STRICT", "1")
    monkeypatch.setenv("TEXTTOCAD_ALLOW_EXTERNAL_LLM", "1")
    s = config.Settings.load()
    assert s.active_model_tier == "3b"
    assert s.airgap_strict is True
    # Strict air-gap must force external LLM off even if the user asked for it (SPEC 9.5).
    assert s.allow_external_llm is False


def test_settings_roundtrip(monkeypatch, tmp_path: Path):
    cfg = tmp_path / "cfg.json"
    monkeypatch.setenv("TEXTTOCAD_CONFIG", str(cfg))
    # Ensure a clean env for the reload assertion.
    for var in ("TEXTTOCAD_MODEL_TIER", "AIRGAP_STRICT", "TEXTTOCAD_AIRGAP_STRICT"):
        monkeypatch.delenv(var, raising=False)
    s = config.Settings.load()
    s.active_model_tier = "14b"
    s.material = "aluminium"
    saved = s.save()
    assert saved.exists()
    assert os.path.getsize(saved) > 0
    reloaded = config.Settings.load()
    assert reloaded.active_model_tier == "14b"
    assert reloaded.material == "aluminium"


def test_material_densities_present():
    assert config.MATERIAL_DENSITIES["mild_steel"] == 7850.0
    assert set(config.MATERIAL_DENSITIES) == {"mild_steel", "aluminium", "stainless"}
