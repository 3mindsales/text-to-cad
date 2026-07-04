"""Builders produce a valid solid across each part's parameter range (SPEC 5.4/5.5, AC2).

Requires CadQuery; skipped automatically if it is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("cadquery")

from texttocad.geometry import builders, validate  # noqa: E402

CASES = {
    "FLAT_PLATE": [
        dict(length=50, width=30, thickness=2),
        dict(
            length=200,
            width=100,
            thickness=5,
            edge_fillet=6,
            hole_pattern=dict(
                kind="grid", hole_dia=6, rows=2, cols=4, pitch_x=25, pitch_y=25, edge_margin=15
            ),
        ),
        dict(length=1000, width=800, thickness=20),
    ],
    "L_BRACKET": [
        dict(leg_a_length=40, leg_b_length=40, width=30, thickness=3),
        dict(
            leg_a_length=150,
            leg_b_length=80,
            width=80,
            thickness=6,
            inner_fillet=8,
            holes_a=dict(dia=9, count=2),
            holes_b=dict(dia=9, count=2),
        ),
        dict(leg_a_length=500, leg_b_length=400, width=200, thickness=20, inner_fillet=15),
    ],
    "BASE_PLATE": [
        dict(length=100, width=100, thickness=8, corner_hole_dia=10, corner_edge_margin=15),
        dict(
            length=250,
            width=250,
            thickness=20,
            corner_hole_dia=22,
            corner_edge_margin=40,
            central_bore_dia=60,
        ),
        dict(length=600, width=400, thickness=30, corner_hole_dia=26, corner_edge_margin=50),
    ],
    "GUSSET": [
        dict(edge_a=80, edge_b=80, thickness=6, hypotenuse="straight"),
        dict(edge_a=120, edge_b=120, thickness=8, hypotenuse="curved", radius=140, hole_dia=14, hole_count=2),
        dict(edge_a=300, edge_b=200, thickness=12, hypotenuse="straight"),
    ],
    "FLANGE": [
        dict(
            outer_dia=100, inner_bore_dia=50, thickness=8, bolt_circle_dia=80, bolt_count=4, bolt_hole_dia=9
        ),
        dict(
            outer_dia=220,
            inner_bore_dia=110,
            thickness=20,
            bolt_circle_dia=180,
            bolt_count=8,
            bolt_hole_dia=18,
        ),
        dict(
            outer_dia=500,
            inner_bore_dia=300,
            thickness=30,
            bolt_circle_dia=420,
            bolt_count=12,
            bolt_hole_dia=26,
        ),
    ],
    "BOX_ENCLOSURE": [
        dict(length=80, width=60, height=40, wall_thickness=2, open_top=True),
        dict(length=400, width=300, height=250, wall_thickness=3, open_top=True, drain_dia=20),
        dict(length=800, width=600, height=500, wall_thickness=8, open_top=False),
    ],
}


@pytest.mark.parametrize("part_type", list(CASES))
def test_each_part_builds_valid_solid(part_type):
    for params in CASES[part_type]:
        wp = builders.build(part_type, params)
        result = validate.validate_solid(wp)
        assert result.ok, f"{part_type} {params} -> {result.errors}"
        assert result.volume > 0


def test_determinism_byte_identical_step(tmp_path):
    from texttocad.geometry import exporters

    params = dict(length=150, width=80, thickness=6)
    a = exporters.export_step(builders.build("FLAT_PLATE", params), tmp_path / "a.step")
    b = exporters.export_step(builders.build("FLAT_PLATE", params), tmp_path / "b.step")
    assert a.read_bytes() == b.read_bytes()
