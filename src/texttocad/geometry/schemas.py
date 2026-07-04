"""Pydantic v2 schemas for the six MVP part types (SPEC 5.4).

Every value is in millimetres. Field constraints reject absurd values early (SPEC 12 S5);
cross-field ``model_validator``s enforce the relationships from SPEC 5.4 and REJECT rather
than silently clamp. ``PART_SCHEMAS`` maps a part_type id to its model.

The part origin/datum is documented per model. These schemas are the validated
*specification* — the single source of truth (I2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from texttocad.config import MAX_PART_ENVELOPE_MM

_ENV = MAX_PART_ENVELOPE_MM


class PartSchema(BaseModel):
    """Base for all part schemas — forbids unknown keys so typos are caught."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Shared sub-models                                                           #
# --------------------------------------------------------------------------- #


class HolePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["grid", "linear"] = "grid"
    hole_dia: float = Field(gt=0, le=_ENV)
    rows: int = Field(ge=1, le=100)
    cols: int = Field(ge=1, le=100)
    pitch_x: float = Field(gt=0, le=_ENV)
    pitch_y: float = Field(gt=0, le=_ENV)
    edge_margin: float = Field(ge=0, le=_ENV)


class HoleGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dia: float = Field(gt=0, le=_ENV)
    count: int = Field(ge=1, le=100)


# --------------------------------------------------------------------------- #
# FLAT_PLATE — datum: centre of the plate, bottom face on z=0                  #
# --------------------------------------------------------------------------- #


class FlatPlate(PartSchema):
    length: float = Field(gt=0, le=_ENV)
    width: float = Field(gt=0, le=_ENV)
    thickness: float = Field(gt=0, le=_ENV)
    edge_fillet: float | None = Field(default=None, ge=0, le=_ENV)
    hole_pattern: HolePattern | None = None

    @model_validator(mode="after")
    def _check(self) -> FlatPlate:
        if self.thickness >= min(self.length, self.width):
            raise ValueError("thickness must be less than the plate's length and width")
        if self.edge_fillet is not None and self.edge_fillet * 2 >= min(self.length, self.width):
            raise ValueError("edge_fillet is too large for the plate")
        hp = self.hole_pattern
        if hp is not None:
            span_x = (hp.cols - 1) * hp.pitch_x + hp.hole_dia + 2 * hp.edge_margin
            span_y = (hp.rows - 1) * hp.pitch_y + hp.hole_dia + 2 * hp.edge_margin
            if span_x > self.length or span_y > self.width:
                raise ValueError("hole pattern does not fit within the plate with the given margins")
        return self


# --------------------------------------------------------------------------- #
# L_BRACKET — datum: inner corner at origin; leg A along +X, leg B along +Z    #
# --------------------------------------------------------------------------- #


class LBracket(PartSchema):
    leg_a_length: float = Field(gt=0, le=_ENV)
    leg_b_length: float = Field(gt=0, le=_ENV)
    width: float = Field(gt=0, le=_ENV)
    thickness: float = Field(gt=0, le=_ENV)
    inner_fillet: float = Field(default=0, ge=0, le=_ENV)
    holes_a: HoleGroup | None = None
    holes_b: HoleGroup | None = None

    @model_validator(mode="after")
    def _check(self) -> LBracket:
        if self.thickness >= min(self.leg_a_length, self.leg_b_length):
            raise ValueError("thickness must be less than each leg length")
        if self.inner_fillet >= min(self.leg_a_length, self.leg_b_length) - self.thickness:
            raise ValueError("inner_fillet is too large for the legs")
        for grp, leg in ((self.holes_a, self.leg_a_length), (self.holes_b, self.leg_b_length)):
            if grp is not None:
                if grp.dia >= self.width:
                    raise ValueError("hole diameter must be smaller than the bracket width")
                if grp.dia * grp.count >= leg:
                    raise ValueError("holes do not fit along the leg")
        return self


# --------------------------------------------------------------------------- #
# BASE_PLATE — datum: centre; bottom face on z=0                               #
# --------------------------------------------------------------------------- #


class BasePlate(PartSchema):
    length: float = Field(gt=0, le=_ENV)
    width: float = Field(gt=0, le=_ENV)
    thickness: float = Field(gt=0, le=_ENV)
    corner_hole_dia: float = Field(gt=0, le=_ENV)
    corner_edge_margin: float = Field(gt=0, le=_ENV)
    central_bore_dia: float | None = Field(default=None, gt=0, le=_ENV)

    @model_validator(mode="after")
    def _check(self) -> BasePlate:
        if self.thickness >= min(self.length, self.width):
            raise ValueError("thickness must be less than the plate's length and width")
        if self.corner_hole_dia + 2 * self.corner_edge_margin >= min(self.length, self.width):
            raise ValueError("corner holes + margins do not fit on the plate")
        if self.central_bore_dia is not None and self.central_bore_dia >= min(self.length, self.width):
            raise ValueError("central bore is larger than the plate")
        return self


# --------------------------------------------------------------------------- #
# GUSSET — datum: right-angle corner at origin; edge A +X, edge B +Z           #
# --------------------------------------------------------------------------- #


class Gusset(PartSchema):
    edge_a: float = Field(gt=0, le=_ENV)
    edge_b: float = Field(gt=0, le=_ENV)
    thickness: float = Field(gt=0, le=_ENV)
    hypotenuse: Literal["straight", "curved"] = "straight"
    radius: float | None = Field(default=None, gt=0, le=_ENV)
    hole_dia: float | None = Field(default=None, gt=0, le=_ENV)
    hole_count: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def _check(self) -> Gusset:
        if self.thickness >= min(self.edge_a, self.edge_b):
            raise ValueError("thickness must be less than each edge length")
        if self.hypotenuse == "curved" and self.radius is None:
            raise ValueError("a curved hypotenuse requires a radius")
        if self.hypotenuse == "curved" and self.radius is not None:
            if self.radius < max(self.edge_a, self.edge_b) / 2:
                raise ValueError("radius is too small to span the hypotenuse")
        if self.hole_dia is not None and self.hole_dia >= min(self.edge_a, self.edge_b) / 2:
            raise ValueError("hole diameter is too large for the gusset")
        return self


# --------------------------------------------------------------------------- #
# FLANGE — datum: centre; bottom face on z=0; axis = Z                         #
# --------------------------------------------------------------------------- #


class Flange(PartSchema):
    outer_dia: float = Field(gt=0, le=_ENV)
    inner_bore_dia: float = Field(gt=0, le=_ENV)
    thickness: float = Field(gt=0, le=_ENV)
    bolt_circle_dia: float = Field(gt=0, le=_ENV)
    bolt_count: int = Field(ge=2, le=100)
    bolt_hole_dia: float = Field(gt=0, le=_ENV)

    @model_validator(mode="after")
    def _check(self) -> Flange:
        if self.inner_bore_dia >= self.outer_dia:
            raise ValueError("inner bore must be smaller than the outer diameter")
        if not (self.inner_bore_dia < self.bolt_circle_dia < self.outer_dia):
            raise ValueError("bolt circle must lie between the bore and the outer edge")
        # Bolt holes must fit inside the annulus on both sides of the bolt circle.
        clearance_out = (self.outer_dia - self.bolt_circle_dia) / 2
        clearance_in = (self.bolt_circle_dia - self.inner_bore_dia) / 2
        if self.bolt_hole_dia >= 2 * min(clearance_out, clearance_in):
            raise ValueError("bolt holes do not fit within the flange annulus")
        return self


# --------------------------------------------------------------------------- #
# BOX_ENCLOSURE / TANK — datum: centre of the base; base on z=0               #
# --------------------------------------------------------------------------- #


class BoxEnclosure(PartSchema):
    length: float = Field(gt=0, le=_ENV)
    width: float = Field(gt=0, le=_ENV)
    height: float = Field(gt=0, le=_ENV)
    wall_thickness: float = Field(gt=0, le=_ENV)
    open_top: bool = True
    drain_dia: float | None = Field(default=None, gt=0, le=_ENV)

    @model_validator(mode="after")
    def _check(self) -> BoxEnclosure:
        if self.wall_thickness * 2 >= min(self.length, self.width, self.height):
            raise ValueError("walls are too thick for the enclosure size")
        if self.drain_dia is not None and self.drain_dia >= min(self.length, self.width):
            raise ValueError("drain is larger than the base")
        return self


#: Registry: part_type id -> schema model. Keep in sync with builders.BUILDERS.
PART_SCHEMAS: dict[str, type[PartSchema]] = {
    "FLAT_PLATE": FlatPlate,
    "L_BRACKET": LBracket,
    "BASE_PLATE": BasePlate,
    "GUSSET": Gusset,
    "FLANGE": Flange,
    "BOX_ENCLOSURE": BoxEnclosure,
}


def validate_parameters(part_type: str, parameters: dict) -> PartSchema:
    """Validate raw parameters against the schema for ``part_type``.

    Raises KeyError for an unknown part_type and pydantic ValidationError for bad params.
    """
    if part_type not in PART_SCHEMAS:
        raise KeyError(f"unknown part_type '{part_type}'")
    return PART_SCHEMAS[part_type].model_validate(parameters)
