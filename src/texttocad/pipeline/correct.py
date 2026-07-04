"""Natural-language correction loop (SPEC 3.3).

Edits are a DIFF against the current validated specification, not a fresh generation:
the LLM returns ONLY the changed keys (a JSON patch), which we merge, re-validate, and
rebuild. Direct parameter edits (slider/field) bypass the LLM entirely (see state.py).
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from texttocad.llm.base import LLMBackend
from texttocad.pipeline.generate import (
    GenerationOutcome,
    GeometryOps,
    PipelineError,
    Specification,
    default_geometry_ops,
)

_CORRECT_SYSTEM = (
    "You edit an existing CAD parameter specification. You are given the current parameters "
    "and an instruction. Reply with ONLY a JSON object containing the keys that change (a patch). "
    "Do not restate unchanged keys. No prose, no code fences."
)


def apply_correction(
    current: Specification,
    instruction: str,
    backend: LLMBackend,
    *,
    geometry: GeometryOps | None = None,
) -> GenerationOutcome:
    """Apply an NL edit as a JSON patch against the current template spec."""
    ops = geometry or default_geometry_ops()
    if current.mode != "template" or not current.part_type:
        raise PipelineError("natural-language correction is supported for template specs only")

    user = (
        f"Part type: {current.part_type}\n"
        f"Current parameters: {json.dumps(current.parameters, sort_keys=True)}\n"
        f"Instruction: {instruction}\n"
        "Return ONLY the changed keys as a JSON patch."
    )
    patch = backend.generate_json(_CORRECT_SYSTEM, user)
    return apply_patch(current, patch, geometry=ops)


def apply_patch(
    current: Specification,
    patch: dict[str, Any],
    *,
    geometry: GeometryOps | None = None,
) -> GenerationOutcome:
    """Merge a parameter patch, re-validate, and rebuild (also used by direct edits)."""
    ops = geometry or default_geometry_ops()
    from texttocad.geometry import schemas

    part_type = current.part_type
    if not part_type:
        return GenerationOutcome(ok=False, spec=None, solid=None, errors=["spec has no part_type"])

    merged = {**current.parameters, **patch}
    try:
        validated = schemas.validate_parameters(part_type, merged)
        norm = validated.model_dump(exclude_none=True)
        solid = ops.build_template(part_type, norm)
        result = ops.validate_solid(solid)
        if not result.ok:
            raise PipelineError("; ".join(result.errors))
    except Exception as exc:
        # A bad edit does not destroy the current model; the caller keeps the prior spec.
        return GenerationOutcome(ok=False, spec=None, solid=None, errors=[f"{type(exc).__name__}: {exc}"])

    return GenerationOutcome(
        ok=True,
        spec=replace(current, parameters=norm),
        solid=solid,
        warnings=list(result.warnings),
        validation_summary=result.summary(),
    )
