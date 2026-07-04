"""Pipeline: generate + self-repair + correction + history + report (SPEC 3, 6, 8.5).

Uses a stubbed backend and stubbed geometry so no model and no CadQuery are needed —
only the pipeline's control flow and real pydantic schema validation are exercised.
"""

from __future__ import annotations

from types import SimpleNamespace

from texttocad.pipeline import correct, generate, state
from texttocad.pipeline.generate import GeometryOps, Specification


class StubBackend:
    """Returns queued JSON responses; satisfies the LLMBackend surface used here."""

    name = "stub"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def is_available(self):
        return True

    @property
    def is_local(self):
        return True

    def generate_text(self, system, user):
        return ""

    def generate_json(self, system, user, schema_hint=None):
        self.calls += 1
        return self._responses.pop(0)


def _stub_ops(valid=True, errors=None):
    result = SimpleNamespace(
        ok=valid, errors=errors or [], warnings=[], summary=lambda: "stub-valid" if valid else "stub-invalid"
    )
    return GeometryOps(
        build_template=lambda pt, params: SimpleNamespace(kind="solid", pt=pt),
        build_freeform=lambda code: SimpleNamespace(kind="solid"),
        validate_solid=lambda solid: result,
    )


VALID = {
    "mode": "template",
    "part_type": "FLAT_PLATE",
    "parameters": {"length": 100, "width": 100, "thickness": 5},
}
BAD = {
    "mode": "template",
    "part_type": "FLAT_PLATE",
    "parameters": {"length": 10, "width": 10, "thickness": 50},
}


def test_happy_path_zero_repairs():
    out = generate.generate("flat plate", StubBackend([VALID]), geometry=_stub_ops())
    assert out.ok is True
    assert out.repair_attempts == 0
    assert out.spec.part_type == "FLAT_PLATE"
    assert out.spec.parameters["thickness"] == 5


def test_repair_path_one_repair():
    backend = StubBackend([BAD, VALID])  # first fails schema, second valid
    out = generate.generate("flat plate", backend, geometry=_stub_ops(), max_repairs=3)
    assert out.ok is True
    assert out.repair_attempts == 1
    assert backend.calls == 2


def test_exhausted_repairs_no_export():
    backend = StubBackend([BAD, BAD, BAD])
    out = generate.generate("flat plate", backend, geometry=_stub_ops(), max_repairs=2)
    assert out.ok is False
    assert out.solid is None
    assert out.repair_attempts == 2
    assert len(out.errors) == 3  # initial + 2 repairs


def test_geometry_invalid_triggers_failure():
    # Schema passes but the geometry gate rejects -> failure (no valid solid).
    out = generate.generate(
        "flat plate", StubBackend([VALID]), geometry=_stub_ops(valid=False, errors=["bad"]), max_repairs=0
    )
    assert out.ok is False


def test_freeform_disabled_by_default():
    ff = {"mode": "freeform", "code": "result = cq.Workplane('XY').box(1,1,1)"}
    out = generate.generate("weird shape", StubBackend([ff]), geometry=_stub_ops(), max_repairs=0)
    assert out.ok is False  # freeform not allowed -> rejected


def test_correction_changes_only_intended_keys():
    current = Specification(
        mode="template", part_type="FLAT_PLATE", parameters={"length": 100, "width": 100, "thickness": 5}
    )
    out = correct.apply_correction(
        current, "make it 8 mm thick", StubBackend([{"thickness": 8}]), geometry=_stub_ops()
    )
    assert out.ok is True
    assert out.spec.parameters["thickness"] == 8
    assert out.spec.parameters["length"] == 100
    assert out.spec.parameters["width"] == 100


def test_bad_correction_keeps_prior_model():
    current = Specification(
        mode="template", part_type="FLAT_PLATE", parameters={"length": 100, "width": 100, "thickness": 5}
    )
    # Patch drives thickness beyond the plate -> schema rejects -> ok False, no solid.
    out = correct.apply_patch(current, {"thickness": 500}, geometry=_stub_ops())
    assert out.ok is False
    assert out.spec is None


def test_history_undo_redo_restores_specs():
    h = state.SpecHistory()
    s1 = Specification(
        mode="template", part_type="FLAT_PLATE", parameters={"length": 100, "width": 100, "thickness": 5}
    )
    s2 = state.with_param_updates(s1, {"thickness": 8})
    s3 = state.with_param_updates(s2, {"thickness": 10})
    for s in (s1, s2, s3):
        h.push(s)
    assert h.current.parameters["thickness"] == 10
    assert h.undo().parameters["thickness"] == 8
    assert h.undo().parameters["thickness"] == 5
    assert not h.can_undo
    assert h.redo().parameters["thickness"] == 8
    # A new push after undo truncates the redo tail.
    h.push(state.with_param_updates(h.current, {"thickness": 12}))
    assert not h.can_redo
    assert h.current.parameters["thickness"] == 12


def test_history_cap():
    h = state.SpecHistory(cap=3)
    for t in range(5):
        h.push(
            Specification(
                mode="template",
                part_type="FLAT_PLATE",
                parameters={"length": 100, "width": 100, "thickness": t + 1},
            )
        )
    assert len(h) == 3


def test_spec_hash_stable_and_distinct():
    a = Specification(mode="template", part_type="FLAT_PLATE", parameters={"length": 100})
    b = Specification(mode="template", part_type="FLAT_PLATE", parameters={"length": 100})
    c = Specification(mode="template", part_type="FLAT_PLATE", parameters={"length": 200})
    assert a.spec_hash() == b.spec_hash()
    assert a.spec_hash() != c.spec_hash()


def test_report_written(tmp_path):
    from texttocad.reporting.report import ReportData, write_report

    spec = Specification(
        mode="template", part_type="FLAT_PLATE", parameters={"length": 100, "width": 100, "thickness": 5}
    )
    data = ReportData(
        user_prompt="flat plate 100x100x5",
        spec=spec,
        backend_name="ollama",
        model="qwen2.5-coder:7b-instruct",
        is_local=True,
        repair_attempts=0,
        validation_summary="VALID",
        warnings=[],
        timestamp="2026-07-04T00:00:00Z",
    )
    p = write_report(tmp_path / "conversion_report.txt", data)
    text = p.read_text()
    assert "is_local:         True" in text
    assert "FLAT_PLATE" in text
    assert "prompt version" in text
