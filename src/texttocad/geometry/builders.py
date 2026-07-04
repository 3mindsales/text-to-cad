"""Deterministic builders — one per part type (SPEC 5.3/5.4).

Each builder takes a validated schema instance and returns a CadQuery ``Workplane``
holding a single solid. Builders are pure and deterministic: same spec -> same solid ->
byte-identical STEP (I3). No randomness, no time, no global state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import cadquery as cq

from texttocad.geometry import schemas


def _cut_cylinder(
    wp: cq.Workplane,
    center: tuple[float, float, float],
    direction: tuple[float, float, float],
    dia: float,
    length: float,
) -> cq.Workplane:
    """Cut a through-cylinder from ``wp`` — robust alternative to face selection."""
    cyl = cq.Solid.makeCylinder(dia / 2.0, length, cq.Vector(*center), cq.Vector(*direction))
    return wp.cut(cq.Workplane(obj=cyl))


def _grid_points(hp: schemas.HolePattern) -> list[tuple[float, float]]:
    xs = [(i - (hp.cols - 1) / 2.0) * hp.pitch_x for i in range(hp.cols)]
    ys = [(j - (hp.rows - 1) / 2.0) * hp.pitch_y for j in range(hp.rows)]
    return [(x, y) for y in ys for x in xs]


def build_flat_plate(p: schemas.FlatPlate) -> cq.Workplane:
    wp = cq.Workplane("XY").box(p.length, p.width, p.thickness, centered=(True, True, False))
    if p.edge_fillet:
        wp = wp.edges("|Z").fillet(p.edge_fillet)
    if p.hole_pattern is not None:
        pts = _grid_points(p.hole_pattern)
        wp = wp.faces(">Z").workplane().pushPoints(pts).hole(p.hole_pattern.hole_dia)
    return wp


def build_l_bracket(p: schemas.LBracket) -> cq.Workplane:
    t = p.thickness
    profile = [
        (0, 0),
        (p.leg_a_length, 0),
        (p.leg_a_length, t),
        (t, t),
        (t, p.leg_b_length),
        (0, p.leg_b_length),
    ]
    wp = cq.Workplane("XZ").polyline(profile).close().extrude(p.width)
    if p.inner_fillet > 0:
        wp = wp.edges(cq.selectors.NearestToPointSelector((t, p.width / 2.0, t))).fillet(p.inner_fillet)

    # Holes drilled through each leg; positions evenly spaced, centred across the width.
    if p.holes_a is not None:
        n = p.holes_a.count
        x0, x1 = t + p.holes_a.dia, p.leg_a_length - p.holes_a.dia
        for x in _spaced(x0, x1, n):
            wp = _cut_cylinder(wp, (x, p.width / 2.0, -1), (0, 0, 1), p.holes_a.dia, t + 2)
    if p.holes_b is not None:
        n = p.holes_b.count
        z0, z1 = t + p.holes_b.dia, p.leg_b_length - p.holes_b.dia
        for z in _spaced(z0, z1, n):
            wp = _cut_cylinder(wp, (-1, p.width / 2.0, z), (1, 0, 0), p.holes_b.dia, t + 2)
    return wp


def build_base_plate(p: schemas.BasePlate) -> cq.Workplane:
    wp = cq.Workplane("XY").box(p.length, p.width, p.thickness, centered=(True, True, False))
    mx = p.length / 2.0 - p.corner_edge_margin
    my = p.width / 2.0 - p.corner_edge_margin
    corners = [(mx, my), (-mx, my), (mx, -my), (-mx, -my)]
    wp = wp.faces(">Z").workplane().pushPoints(corners).hole(p.corner_hole_dia)
    if p.central_bore_dia is not None:
        wp = wp.faces(">Z").workplane().hole(p.central_bore_dia)
    return wp


def build_gusset(p: schemas.Gusset) -> cq.Workplane:
    base = cq.Workplane("XZ").moveTo(0, 0).lineTo(p.edge_a, 0)
    if p.hypotenuse == "curved" and p.radius is not None:
        base = base.radiusArc((0, p.edge_b), p.radius)
    else:
        base = base.lineTo(0, p.edge_b)
    wp = base.close().extrude(p.thickness)
    if p.hole_dia is not None and p.hole_count:
        # Space holes along the bottom edge, inset so they stay inside the triangle.
        x0, x1 = p.edge_a * 0.2, p.edge_a * 0.6
        z_inset = min(p.edge_b * 0.25, p.hole_dia)
        for x in _spaced(x0, x1, p.hole_count):
            wp = _cut_cylinder(wp, (x, -1, z_inset), (0, 1, 0), p.hole_dia, p.thickness + 2)
    return wp


def build_flange(p: schemas.Flange) -> cq.Workplane:
    wp = cq.Workplane("XY").circle(p.outer_dia / 2.0).extrude(p.thickness)
    wp = wp.faces(">Z").workplane().hole(p.inner_bore_dia)
    wp = (
        wp.faces(">Z")
        .workplane()
        .polarArray(p.bolt_circle_dia / 2.0, 0, 360, p.bolt_count)
        .hole(p.bolt_hole_dia)
    )
    return wp


def build_box_enclosure(p: schemas.BoxEnclosure) -> cq.Workplane:
    box = cq.Workplane("XY").box(p.length, p.width, p.height, centered=(True, True, False))
    if p.open_top:
        wp = box.faces(">Z").shell(-p.wall_thickness)
    else:
        wp = box.shell(-p.wall_thickness)
    if p.drain_dia is not None:
        wp = _cut_cylinder(wp, (0, 0, -1), (0, 0, 1), p.drain_dia, p.wall_thickness + 2)
    return wp


def _spaced(a: float, b: float, n: int) -> list[float]:
    """n points evenly spaced within [a, b] (centre single point)."""
    if n <= 1:
        return [(a + b) / 2.0]
    step = (b - a) / (n - 1)
    return [a + i * step for i in range(n)]


#: Registry: part_type id -> builder. Keep in sync with schemas.PART_SCHEMAS.
BUILDERS: dict[str, Callable[[Any], cq.Workplane]] = {
    "FLAT_PLATE": build_flat_plate,
    "L_BRACKET": build_l_bracket,
    "BASE_PLATE": build_base_plate,
    "GUSSET": build_gusset,
    "FLANGE": build_flange,
    "BOX_ENCLOSURE": build_box_enclosure,
}


def build(part_type: str, parameters: dict) -> cq.Workplane:
    """Validate ``parameters`` against the schema, then build the solid.

    Raises KeyError for an unknown part_type; pydantic ValidationError for bad params.
    """
    spec = schemas.validate_parameters(part_type, parameters)
    return BUILDERS[part_type](spec)


def build_from_spec(spec: schemas.PartSchema) -> cq.Workplane:
    """Build directly from an already-validated schema instance."""
    part_type = next(k for k, v in schemas.PART_SCHEMAS.items() if isinstance(spec, v))
    return BUILDERS[part_type](spec)
