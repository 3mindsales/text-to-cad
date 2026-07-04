"""Headline acceptance test (SPEC 13 / AC1).

On the local path with only the (stubbed) bundled model, the prompt
"L-bracket 150 x 80 x 6 mm, four M8 holes, 8 mm inner fillet" must produce a valid STEP
file and a cut-list CSV with ZERO external sockets opened. A real Ollama model is not
available in CI, so a stub backend supplies the canned spec; the air-gap assertion (no
external sockets) and the deterministic geometry/export path are the real subject.
"""

from __future__ import annotations

import socket

import pytest

pytest.importorskip("cadquery")

from texttocad.geometry import exporters  # noqa: E402
from texttocad.llm.locality import is_local_host  # noqa: E402
from texttocad.pipeline import generate  # noqa: E402


class _SocketGuard:
    """Records every connect() target and flags any non-local address (air-gap proof)."""

    def __init__(self):
        self.external: list[str] = []
        self._orig_connect = socket.socket.connect
        self._orig_connect_ex = socket.socket.connect_ex

    def _check(self, address):
        try:
            host = address[0]
        except (TypeError, IndexError):
            return
        if not is_local_host(str(host)):
            self.external.append(str(host))

    def __enter__(self):
        guard = self

        def connect(self, address):  # noqa: ANN001
            guard._check(address)
            return guard._orig_connect(self, address)

        def connect_ex(self, address):  # noqa: ANN001
            guard._check(address)
            return guard._orig_connect_ex(self, address)

        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        return self

    def __exit__(self, *exc):
        socket.socket.connect = self._orig_connect
        socket.socket.connect_ex = self._orig_connect_ex


class _BundledModelStub:
    """Stands in for the bundled local model; opens no sockets."""

    name = "ollama"
    model_tag = "qwen2.5-coder:7b-instruct"

    @property
    def is_local(self):
        return True

    def generate_json(self, system, user, schema_hint=None):
        return {
            "mode": "template",
            "part_type": "L_BRACKET",
            "parameters": {
                "leg_a_length": 150,
                "leg_b_length": 80,
                "width": 80,
                "thickness": 6,
                "inner_fillet": 8,
                "holes_a": {"dia": 9, "count": 2},
                "holes_b": {"dia": 9, "count": 2},
            },
        }


def test_headline_acceptance_offline(tmp_path):
    prompt = "L-bracket 150 x 80 x 6 mm, four M8 holes, 8 mm inner fillet"
    with _SocketGuard() as guard:
        outcome = generate.generate(prompt, _BundledModelStub())
        assert outcome.ok is True, outcome.errors
        step = exporters.export_step(outcome.solid, tmp_path / "bracket.step")
        csv = exporters.cut_list_csv(outcome.solid, tmp_path / "bracket.csv")

    # Valid STEP (rendered model is the same solid) + cut list.
    assert step.read_text(encoding="utf-8").startswith("ISO-10303-21")
    assert "mass" in csv.read_text(encoding="utf-8")
    # THE air-gap guarantee: no external sockets opened during the local flow.
    assert guard.external == [], f"external sockets opened: {guard.external}"


def test_determinism_byte_identical_step(tmp_path):
    # AC3/I3: the same spec re-exports byte-identical STEP.
    b = _BundledModelStub()
    o1 = generate.generate("bracket", b)
    o2 = generate.generate("bracket", b)
    a = exporters.export_step(o1.solid, tmp_path / "a.step")
    c = exporters.export_step(o2.solid, tmp_path / "c.step")
    assert a.read_bytes() == c.read_bytes()
