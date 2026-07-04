"""Versioned prompt loader (SPEC 4.6)."""

from __future__ import annotations

import pytest

from texttocad.llm import prompts


def test_load_default_prompt():
    bundle = prompts.load_prompt()
    assert bundle.version == "v1"
    assert "JSON" in bundle.system
    assert "MILLIMETRES" in bundle.system
    assert len(bundle.fewshot) >= 4
    # Few-shot examples span multiple part types.
    part_types = {ex["assistant"].get("part_type") for ex in bundle.fewshot}
    assert {"L_BRACKET", "FLAT_PLATE", "FLANGE"} <= part_types


def test_preamble_renders():
    bundle = prompts.load_prompt()
    pre = bundle.build_user_preamble()
    assert "USER:" in pre and "ASSISTANT:" in pre


def test_missing_version_raises():
    with pytest.raises(FileNotFoundError):
        prompts.load_prompt("v999")
