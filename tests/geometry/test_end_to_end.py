"""PR-9 acceptance: build an L-bracket from a schema and write STEP + PDF + CSV offline."""

from __future__ import annotations

import pytest

pytest.importorskip("cadquery")

from texttocad.geometry import builders, exporters, validate  # noqa: E402


def test_l_bracket_full_export(tmp_path):
    params = dict(
        leg_a_length=150,
        leg_b_length=80,
        width=80,
        thickness=6,
        inner_fillet=8,
        holes_a=dict(dia=9, count=2),
        holes_b=dict(dia=9, count=2),
    )
    wp = builders.build("L_BRACKET", params)
    result = validate.validate_solid(wp)
    assert result.ok, result.errors

    step = exporters.export_step(wp, tmp_path / "bracket.step")
    pdf = exporters.drawing_pdf(wp, tmp_path / "bracket.pdf", title="L-Bracket")
    csv = exporters.cut_list_csv(wp, tmp_path / "bracket.csv", material="mild_steel")

    assert step.read_text().startswith("ISO-10303-21")
    assert pdf.read_bytes().startswith(b"%PDF")
    assert "mass" in csv.read_text()
