"""Offline demo: build the acceptance L-bracket and write STEP + drawing + cut list.

Usage:  python scripts/demo_build.py [output_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

from texttocad.geometry import builders, exporters, validate


def main(out_dir: str = "TextToCAD_Output") -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
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
    print("validation:", result.summary())
    if not result.ok:
        print("errors:", result.errors)
        return 1
    print("STEP  ->", exporters.export_step(wp, out / "bracket.step"))
    print("STL   ->", exporters.export_stl(wp, out / "bracket.stl"))
    print("GLB   ->", exporters.export_glb(wp, out / "bracket.glb"))
    print("PDF   ->", exporters.drawing_pdf(wp, out / "bracket.pdf", title="L-Bracket"))
    print("CSV   ->", exporters.cut_list_csv(wp, out / "bracket.csv"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*(sys.argv[1:2])))
