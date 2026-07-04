"""Units: millimetre is the internal working unit (SPEC 5.1).

All schemas, builder math, and exports are in mm. Inch is a DISPLAY-only convenience,
converted at the UI edge — never stored or exported in inch.
"""

from __future__ import annotations

MM_PER_INCH = 25.4


def inch_to_mm(value: float) -> float:
    return value * MM_PER_INCH


def mm_to_inch(value: float) -> float:
    return value / MM_PER_INCH


def to_display(value_mm: float, units: str = "mm") -> float:
    """Convert an internal mm value to the requested display unit."""
    return mm_to_inch(value_mm) if units == "inch" else value_mm


def from_display(value: float, units: str = "mm") -> float:
    """Convert a user-entered display value back to internal mm."""
    return inch_to_mm(value) if units == "inch" else value
