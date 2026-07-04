"""Automatable slice of the SPEC 12 error-scenario matrix (S1-S9).

S1/S7/S8/S9 are integration/manual (see docs/TEST_REPORT_TEMPLATE.md); the rest are
asserted here. Real geometry is used where a build/export is involved.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

pytest.importorskip("cadquery")

from texttocad.geometry import builders, exporters, schemas  # noqa: E402
from texttocad.llm.sandbox import SandboxRejection, validate_code_ast  # noqa: E402
from texttocad.pipeline import generate  # noqa: E402
from texttocad.pipeline.generate import GeometryOps  # noqa: E402


class _StubBackend:
    name = "stub"

    def __init__(self, responses):
        self._responses = list(responses)

    def generate_json(self, system, user, schema_hint=None):
        return self._responses.pop(0)


_GOOD = {
    "mode": "template",
    "part_type": "FLAT_PLATE",
    "parameters": {"length": 100, "width": 100, "thickness": 5},
}
_BAD = {
    "mode": "template",
    "part_type": "FLAT_PLATE",
    "parameters": {"length": 10, "width": 10, "thickness": 50},
}


def test_s2_invalid_then_repaired():
    # S2: non-conforming schema routes into the self-repair loop, then succeeds.
    out = generate.generate("plate", _StubBackend([_BAD, _GOOD]), max_repairs=3)
    assert out.ok is True
    assert out.repair_attempts == 1


def test_s3_freeform_ast_rejected():
    # S3: malicious freeform code is rejected by the AST whitelist (never executed).
    with pytest.raises(SandboxRejection):
        validate_code_ast("import os\nos.system('x')")


def test_s4_invalid_geometry_no_export():
    # S4: schema passes but the geometry gate fails -> failure, no solid to export.
    invalid = SimpleNamespace(ok=False, errors=["self-intersection"], warnings=[], summary=lambda: "invalid")
    ops = GeometryOps(
        build_template=lambda pt, p: object(),
        build_freeform=lambda c: object(),
        validate_solid=lambda s: invalid,
    )
    out = generate.generate("plate", _StubBackend([_GOOD]), geometry=ops, max_repairs=0)
    assert out.ok is False
    assert out.solid is None


def test_s5_out_of_envelope_rejected():
    # S5: a 50 m plate is rejected at schema validation; it never builds.
    with pytest.raises(ValidationError):
        schemas.FlatPlate(length=50000, width=100, thickness=5)


def test_s6_unwritable_output_surfaces_error(tmp_path):
    # S6: exporting into a non-existent parent folder raises (the app catches + prompts).
    wp = builders.build("FLAT_PLATE", {"length": 100, "width": 100, "thickness": 5})
    missing = tmp_path / "does_not_exist" / "cut.csv"
    with pytest.raises(OSError):
        exporters.cut_list_csv(wp, missing)


def test_constrained_3b_forces_template():
    # Constrained-machine pass: on the 3b tier Freeform is disabled (SPEC 4.2).
    from texttocad.config import HardwareInfo, Settings
    from texttocad.llm import router

    hw = HardwareInfo(total_ram_gb=4.0, vram_gb=None, has_nvidia_gpu=False, recommended_tier="3b")
    assert router.freeform_allowed(Settings(active_model_tier="3b", freeform_enabled=True), hw) is False


def test_cloud_boost_is_nonlocal_badge():
    # Cloud "Boost" must classify as non-local (drives the ONLINE LLM ACTIVE badge, I4).
    from texttocad.config import Settings
    from texttocad.llm import router

    b = router.cloud_boost_backend(Settings(allow_external_llm=True, airgap_strict=False))
    assert b.is_local is False
