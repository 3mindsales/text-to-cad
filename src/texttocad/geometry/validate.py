"""Geometry validation gate (SPEC 5.5) — every build must pass this before export (I5).

Hard failures (``ok = False``): invalid B-rep, non-positive/non-finite volume, wrong
solid count, or a bounding box outside the envelope guard. Manufacturability issues
(thin walls, holes near an edge) are WARNINGS, not failures — they surface in the UI and
the report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cadquery as cq

from texttocad.config import MAX_PART_ENVELOPE_MM, MIN_WALL_MM


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    volume: float = 0.0
    bbox: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def summary(self) -> str:
        state = "VALID" if self.ok else "INVALID"
        return f"{state} (volume={self.volume:.1f} mm^3, bbox={self.bbox})"


def validate_solid(
    wp: cq.Workplane,
    *,
    allow_multi_solid: bool = False,
    max_envelope_mm: float = MAX_PART_ENVELOPE_MM,
    min_wall_mm: float = MIN_WALL_MM,
) -> ValidationResult:
    """Run the geometry gate on a built Workplane."""
    errors: list[str] = []
    warnings: list[str] = []

    solids = wp.solids().vals()
    if not solids:
        return ValidationResult(ok=False, errors=["result contains no solid"])

    if not allow_multi_solid and len(solids) != 1:
        errors.append(f"expected exactly one solid, found {len(solids)}")

    shape = wp.val()
    try:
        valid = bool(shape.isValid())
    except Exception as exc:  # pragma: no cover - defensive against OCC quirks
        valid = False
        errors.append(f"isValid() raised: {exc}")
    if not valid:
        errors.append("OCC BRepCheck reports an invalid shape")

    try:
        volume = float(shape.Volume())
    except Exception as exc:  # pragma: no cover
        volume = 0.0
        errors.append(f"Volume() raised: {exc}")
    if not math.isfinite(volume) or volume <= 0:
        errors.append("volume must be finite and positive")

    bb = shape.BoundingBox()
    dims = (bb.xlen, bb.ylen, bb.zlen)
    if max(dims) > max_envelope_mm:
        errors.append(
            f"bounding box {tuple(round(d, 1) for d in dims)} mm exceeds the "
            f"{max_envelope_mm:.0f} mm envelope"
        )

    # Manufacturability WARNINGS (do not fail the gate).
    if min(dims) < min_wall_mm:
        warnings.append(f"smallest overall dimension {min(dims):.2f} mm is below MIN_WALL {min_wall_mm} mm")

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        volume=volume,
        bbox=(round(dims[0], 3), round(dims[1], 3), round(dims[2], 3)),
    )
