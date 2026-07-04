"""Exporters (SPEC 8): STEP/DXF (CAD-grade) + STL/GLB (derived) + drawing + cut list.

The B-rep solid is the source of truth; mesh outputs (STL/GLB) are derived FROM it and
are never authoritative (I2). STEP output is normalised so the same specification yields
byte-identical bytes (I3) — the only volatile field OCC writes is the FILE_NAME header
(path + timestamp), which we replace with a fixed canonical line.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import cadquery as cq

from texttocad.config import LINEAR_DEFLECTION_MM, MATERIAL_DENSITIES
from texttocad.geometry import schemas

_FIXED_FILE_NAME = "FILE_NAME('texttocad','',('texttocad'),(''),'texttocad','texttocad','');"


# --------------------------------------------------------------------------- #
# STEP (AP214) — exact B-rep, deterministic                                   #
# --------------------------------------------------------------------------- #


def export_step(wp: cq.Workplane, path: str | Path) -> Path:
    path = Path(path)
    cq.exporters.export(wp, str(path), cq.exporters.ExportTypes.STEP)
    _normalize_step(path)
    return path


def _normalize_step(path: Path) -> None:
    """Strip volatile fields so the same spec yields byte-identical STEP (I3).

    Two OCC-written volatiles: the FILE_NAME header (path + timestamp) and a per-process
    incrementing counter appended to the translator PRODUCT name (``... 7.7 1``, ``... 2``).
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"FILE_NAME\([^;]*\);", _FIXED_FILE_NAME, text, count=1, flags=re.DOTALL)
    text = re.sub(r"(Open CASCADE STEP translator [\d.]+) \d+", r"\1", text)
    path.write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# STL / GLB — derived mesh (Y-up for AR parity, SPEC 8.2)                      #
# --------------------------------------------------------------------------- #


def export_stl(wp: cq.Workplane, path: str | Path, tolerance: float = LINEAR_DEFLECTION_MM) -> Path:
    path = Path(path)
    cq.exporters.export(wp, str(path), cq.exporters.ExportTypes.STL, tolerance=tolerance)
    return path


def export_glb(wp: cq.Workplane, path: str | Path, tolerance: float = LINEAR_DEFLECTION_MM) -> Path:
    """Tessellate -> trimesh -> GLB, converted to Y-up for ARKit parity."""
    import numpy as np
    import trimesh

    verts, tris = wp.val().tessellate(tolerance)
    vertices = np.array([[v.x, v.y, v.z] for v in verts], dtype=float)
    faces = np.array(tris, dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Z-up (OCC) -> Y-up (glTF/ARKit): rotate -90 deg about X.
    rot = trimesh.transformations.rotation_matrix(-math.pi / 2.0, [1, 0, 0])
    mesh.apply_transform(rot)
    path = Path(path)
    mesh.export(str(path))
    return path


# --------------------------------------------------------------------------- #
# DXF (2D true shape for plate parts) — for laser/plasma/waterjet             #
# --------------------------------------------------------------------------- #


def export_dxf(spec: schemas.PartSchema, path: str | Path) -> Path:
    """Export a 2D true-shape outline + holes for flat/plate parts (SPEC 8.1).

    Supported for FLAT_PLATE and BASE_PLATE (the flat parts). Raises ValueError for
    non-flat part types, which have no meaningful single-plane true shape.
    """
    import ezdxf

    path = Path(path)
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()

    if isinstance(spec, schemas.FlatPlate):
        _dxf_rectangle(msp, spec.length, spec.width)
        if spec.hole_pattern is not None:
            from texttocad.geometry.builders import _grid_points

            for x, y in _grid_points(spec.hole_pattern):
                msp.add_circle((x, y), spec.hole_pattern.hole_dia / 2.0)
    elif isinstance(spec, schemas.BasePlate):
        _dxf_rectangle(msp, spec.length, spec.width)
        mx = spec.length / 2.0 - spec.corner_edge_margin
        my = spec.width / 2.0 - spec.corner_edge_margin
        for x, y in [(mx, my), (-mx, my), (mx, -my), (-mx, -my)]:
            msp.add_circle((x, y), spec.corner_hole_dia / 2.0)
        if spec.central_bore_dia is not None:
            msp.add_circle((0, 0), spec.central_bore_dia / 2.0)
    else:
        raise ValueError(f"DXF true-shape export is only supported for flat parts, not {type(spec).__name__}")

    doc.saveas(str(path))
    return path


def _dxf_rectangle(msp, length: float, width: float) -> None:
    hx, hy = length / 2.0, width / 2.0
    msp.add_lwpolyline([(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)], close=True)


# --------------------------------------------------------------------------- #
# Cut list / takeoff (SPEC 8.4)                                               #
# --------------------------------------------------------------------------- #


def cut_list_csv(wp: cq.Workplane, path: str | Path, material: str = "mild_steel") -> Path:
    """Write a single-part cut list: bounding stock, cut length, area, mass."""
    path = Path(path)
    shape = wp.val()
    bb = shape.BoundingBox()
    dims = (bb.xlen, bb.ylen, bb.zlen)
    volume_mm3 = float(shape.Volume())
    density = MATERIAL_DENSITIES.get(material, MATERIAL_DENSITIES["mild_steel"])
    mass_kg = volume_mm3 / 1e9 * density  # mm^3 -> m^3 * kg/m^3
    cut_length = max(dims)
    face_area = dims[0] * dims[1]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["field", "value", "unit"])
        writer.writerow(["material", material, ""])
        writer.writerow(["stock_length", round(dims[0], 2), "mm"])
        writer.writerow(["stock_width", round(dims[1], 2), "mm"])
        writer.writerow(["stock_height", round(dims[2], 2), "mm"])
        writer.writerow(["cut_length", round(cut_length, 2), "mm"])
        writer.writerow(["face_area", round(face_area, 2), "mm^2"])
        writer.writerow(["volume", round(volume_mm3, 2), "mm^3"])
        writer.writerow(["mass", round(mass_kg, 3), "kg"])
    return path


# --------------------------------------------------------------------------- #
# Fabrication drawing (Phase 1 basic: dims + hole schedule + ortho boxes)      #
# --------------------------------------------------------------------------- #


def drawing_pdf(wp: cq.Workplane, path: str | Path, title: str = "TextToCAD Part") -> Path:
    """Basic Phase-1 drawing: A4 titleblock, overall dimensions, three ortho boxes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path = Path(path)
    bb = wp.val().BoundingBox()
    dims = (bb.xlen, bb.ylen, bb.zlen)

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    margin = 40
    # Titleblock
    c.setLineWidth(1)
    c.rect(margin, margin, w - 2 * margin, h - 2 * margin)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin + 12, h - margin - 24, title)
    c.setFont("Helvetica", 10)
    c.drawString(margin + 12, h - margin - 44, f"Overall: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")

    # Three orthographic bounding boxes (front / top / right) — Phase-1 basic.
    scale = min((w - 2 * margin - 120) / (dims[0] + dims[1] + 1), 3.0)
    y0 = h / 2
    x = margin + 40
    for label, (dx, dy) in [
        ("FRONT", (dims[0], dims[2])),
        ("TOP", (dims[0], dims[1])),
        ("RIGHT", (dims[1], dims[2])),
    ]:
        bw, bh = dx * scale, dy * scale
        c.rect(x, y0, bw, bh)
        c.setFont("Helvetica", 8)
        c.drawString(x, y0 - 12, f"{label}  {dx:.0f} x {dy:.0f}")
        x += bw + 40

    c.showPage()
    c.save()
    return path


def is_finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0
