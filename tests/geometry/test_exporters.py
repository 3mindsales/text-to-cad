"""Exporters produce non-empty, parseable outputs; cut-list math is correct (SPEC 8)."""

from __future__ import annotations

import pytest

pytest.importorskip("cadquery")

from texttocad.geometry import builders, exporters, schemas  # noqa: E402


def _plate():
    return builders.build("FLAT_PLATE", dict(length=100, width=100, thickness=10))


def test_step_is_valid_and_nonempty(tmp_path):
    p = exporters.export_step(_plate(), tmp_path / "p.step")
    text = p.read_text(encoding="utf-8")
    assert text.startswith("ISO-10303-21")
    assert "FILE_NAME('texttocad'" in text  # normalised header
    assert p.stat().st_size > 0


def test_stl_nonempty(tmp_path):
    p = exporters.export_stl(_plate(), tmp_path / "p.stl")
    assert p.stat().st_size > 0


def test_glb_loadable_yup(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    p = exporters.export_glb(_plate(), tmp_path / "p.glb")
    assert p.stat().st_size > 0
    # GLB loads as a Scene; force a single concatenated mesh to inspect geometry.
    loaded = trimesh.load(str(p), force="mesh")
    assert loaded.vertices.shape[0] > 0


def test_dxf_plate_parseable(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    spec = schemas.FlatPlate(
        length=200,
        width=100,
        thickness=5,
        hole_pattern=dict(kind="grid", hole_dia=6, rows=2, cols=3, pitch_x=30, pitch_y=30, edge_margin=15),
    )
    p = exporters.export_dxf(spec, tmp_path / "p.dxf")
    doc = ezdxf.readfile(str(p))
    entities = list(doc.modelspace())
    kinds = {e.dxftype() for e in entities}
    assert "CIRCLE" in kinds  # holes present
    assert "LWPOLYLINE" in kinds  # outline present


def test_dxf_rejects_non_flat():
    spec = schemas.Flange(
        outer_dia=100, inner_bore_dia=50, thickness=8, bolt_circle_dia=80, bolt_count=4, bolt_hole_dia=9
    )
    with pytest.raises(ValueError):
        exporters.export_dxf(spec, "unused.dxf")


def test_cut_list_mass_matches_hand_calc(tmp_path):
    # 100 x 100 x 10 mm mild steel plate = 1e-4 m^3 * 7850 = 0.785 kg.
    p = exporters.cut_list_csv(_plate(), tmp_path / "cut.csv", material="mild_steel")
    rows = {r.split(",")[0]: r.split(",")[1] for r in p.read_text().splitlines()[1:]}
    assert abs(float(rows["mass"]) - 0.785) < 0.02
    assert float(rows["cut_length"]) == pytest.approx(100.0, abs=0.5)


def test_drawing_pdf_nonempty(tmp_path):
    pytest.importorskip("reportlab")
    p = exporters.drawing_pdf(_plate(), tmp_path / "dwg.pdf", title="Test Plate")
    assert p.stat().st_size > 0
    assert p.read_bytes().startswith(b"%PDF")
