"""Pipeline integration with the REAL CadQuery geometry engine (skipped without it).

Exercises default_geometry_ops end-to-end for both Template and Freeform modes, so the
full boundary (LLM spec -> schema -> build -> geometry gate) is proven with real geometry.
"""

from __future__ import annotations

import pytest

pytest.importorskip("cadquery")

from texttocad.pipeline import correct, generate  # noqa: E402
from texttocad.pipeline.generate import Specification  # noqa: E402


class _Backend:
    name = "stub"

    def __init__(self, response):
        self._response = response

    def is_available(self):
        return True

    @property
    def is_local(self):
        return True

    def generate_text(self, s, u):
        return ""

    def generate_json(self, s, u, schema_hint=None):
        return self._response


def test_template_end_to_end_real_geometry():
    resp = {
        "mode": "template",
        "part_type": "FLAT_PLATE",
        "parameters": {"length": 150, "width": 80, "thickness": 6},
    }
    out = generate.generate("flat plate", _Backend(resp))
    assert out.ok is True
    assert out.repair_attempts == 0
    assert "VALID" in out.validation_summary


def test_freeform_end_to_end_real_geometry():
    resp = {"mode": "freeform", "code": "result = cq.Workplane('XY').box(20, 20, 5)"}
    out = generate.generate("a small block", _Backend(resp), allow_freeform=True)
    assert out.ok is True
    assert out.spec.mode == "freeform"


def test_correction_real_geometry():
    current = Specification(
        mode="template", part_type="FLAT_PLATE", parameters={"length": 150, "width": 80, "thickness": 6}
    )
    out = correct.apply_correction(current, "make it 10 mm thick", _Backend({"thickness": 10}))
    assert out.ok is True
    assert out.spec.parameters["thickness"] == 10
