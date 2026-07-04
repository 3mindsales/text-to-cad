"""Schema validation + cross-field rejection tests (SPEC 5.4). No CadQuery needed."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from texttocad.geometry import schemas


def test_valid_instances_for_each_type():
    schemas.FlatPlate(length=200, width=100, thickness=5)
    schemas.LBracket(leg_a_length=150, leg_b_length=80, width=80, thickness=6, inner_fillet=8)
    schemas.BasePlate(length=250, width=250, thickness=20, corner_hole_dia=22, corner_edge_margin=40)
    schemas.Gusset(edge_a=120, edge_b=120, thickness=8)
    schemas.Flange(
        outer_dia=220, inner_bore_dia=110, thickness=20, bolt_circle_dia=180, bolt_count=8, bolt_hole_dia=18
    )
    schemas.BoxEnclosure(length=400, width=300, height=250, wall_thickness=3, open_top=True)


def test_registry_matches():
    assert set(schemas.PART_SCHEMAS) == {
        "FLAT_PLATE",
        "L_BRACKET",
        "BASE_PLATE",
        "GUSSET",
        "FLANGE",
        "BOX_ENCLOSURE",
    }


@pytest.mark.parametrize(
    "ctor,kwargs",
    [
        # thickness >= min(length,width)
        (schemas.FlatPlate, dict(length=50, width=40, thickness=40)),
        # negative / zero rejected by Field
        (schemas.FlatPlate, dict(length=100, width=100, thickness=-1)),
        # out-of-envelope (50 m plate)
        (schemas.FlatPlate, dict(length=50000, width=100, thickness=5)),
        # L-bracket thickness >= leg
        (schemas.LBracket, dict(leg_a_length=10, leg_b_length=80, width=80, thickness=10)),
        # flange bore >= outer
        (
            schemas.Flange,
            dict(
                outer_dia=100,
                inner_bore_dia=120,
                thickness=10,
                bolt_circle_dia=90,
                bolt_count=4,
                bolt_hole_dia=8,
            ),
        ),
        # flange bolt circle outside annulus
        (
            schemas.Flange,
            dict(
                outer_dia=200,
                inner_bore_dia=100,
                thickness=10,
                bolt_circle_dia=210,
                bolt_count=4,
                bolt_hole_dia=8,
            ),
        ),
        # box walls too thick
        (schemas.BoxEnclosure, dict(length=20, width=20, height=20, wall_thickness=15)),
        # gusset curved without radius
        (schemas.Gusset, dict(edge_a=120, edge_b=120, thickness=8, hypotenuse="curved")),
    ],
)
def test_cross_field_rejections(ctor, kwargs):
    with pytest.raises(ValidationError):
        ctor(**kwargs)


def test_extra_keys_forbidden():
    with pytest.raises(ValidationError):
        schemas.FlatPlate(length=100, width=100, thickness=5, bogus=1)


def test_validate_parameters_unknown_type():
    with pytest.raises(KeyError):
        schemas.validate_parameters("NOT_A_PART", {})


def test_hole_pattern_must_fit():
    with pytest.raises(ValidationError):
        schemas.FlatPlate(
            length=100,
            width=100,
            thickness=5,
            hole_pattern=dict(
                kind="grid", hole_dia=10, rows=2, cols=10, pitch_x=30, pitch_y=30, edge_margin=10
            ),
        )
