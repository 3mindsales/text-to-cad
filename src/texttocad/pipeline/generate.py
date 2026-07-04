"""Generation pipeline (SPEC 3.2): intent -> validate -> build -> validate -> self-repair.

The *specification* is the single source of truth (I2); the solid is derived. Geometry
operations are injected via ``GeometryOps`` so the pipeline's control flow (validation
routing + the self-repair loop) is unit-testable without CadQuery — the default ops
lazy-import the real geometry engine.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from texttocad.config import LLM_MAX_REPAIRS
from texttocad.llm.base import LLMBackend
from texttocad.llm.prompts import load_prompt
from texttocad.llm.sandbox import SandboxRejection


class PipelineError(RuntimeError):
    """A build or geometry-validation failure inside the pipeline."""


@dataclass(frozen=True)
class Specification:
    """The validated specification — single source of truth (I2)."""

    mode: str  # "template" | "freeform"
    part_type: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    code: str | None = None
    prompt_version: str = "v1"

    def canonical(self) -> str:
        payload = {
            "mode": self.mode,
            "part_type": self.part_type,
            "parameters": self.parameters,
            "code": self.code,
            "prompt_version": self.prompt_version,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def spec_hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()[:16]


@dataclass
class GeometryOps:
    """Injectable geometry operations (defaults lazy-import the real engine)."""

    build_template: Callable[[str, dict], Any]
    build_freeform: Callable[[str], Any]
    validate_solid: Callable[[Any], Any]


def default_geometry_ops() -> GeometryOps:
    """Wire the real CadQuery-backed engine (imported lazily to keep imports light)."""

    def _build_template(part_type: str, params: dict) -> Any:
        from texttocad.geometry import builders

        return builders.build(part_type, params)

    def _build_freeform(code: str) -> Any:
        import cadquery as cq

        from texttocad.llm.sandbox import run_freeform

        step_path = run_freeform(code)
        return cq.importers.importStep(str(step_path))

    def _validate(solid: Any) -> Any:
        from texttocad.geometry import validate

        return validate.validate_solid(solid)

    return GeometryOps(_build_template, _build_freeform, _validate)


@dataclass
class GenerationOutcome:
    ok: bool
    spec: Specification | None
    solid: Any | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    repair_attempts: int = 0
    validation_summary: str = ""


def _parse_response(raw: dict) -> Specification:
    mode = raw.get("mode", "template")
    if mode == "freeform":
        return Specification(mode="freeform", code=raw.get("code", ""))
    return Specification(
        mode="template",
        part_type=raw.get("part_type"),
        parameters=raw.get("parameters", {}) or {},
    )


def generate(
    user_prompt: str,
    backend: LLMBackend,
    *,
    prompt_version: str = "v1",
    allow_freeform: bool = False,
    max_repairs: int = LLM_MAX_REPAIRS,
    geometry: GeometryOps | None = None,
) -> GenerationOutcome:
    """Run the full generation pipeline with the self-repair loop (SPEC 3.2)."""
    ops = geometry or default_geometry_ops()
    bundle = load_prompt(prompt_version)
    system = bundle.system
    preamble = bundle.build_user_preamble()

    last_error = ""
    errors: list[str] = []
    for attempt in range(max_repairs + 1):
        if attempt == 0:
            user = f"{preamble}\n\nUSER: {user_prompt}\nASSISTANT:"
        else:
            user = (
                f"{preamble}\n\nUSER: {user_prompt}\n"
                f"Your previous answer failed validation with this error:\n{last_error}\n"
                f"Return a corrected JSON specification.\nASSISTANT:"
            )
        try:
            raw = backend.generate_json(system, user)
            spec = _parse_response(raw)
            spec, solid = _build(spec, ops, allow_freeform)
            result = ops.validate_solid(solid)
            if not result.ok:
                raise PipelineError("; ".join(result.errors))
            return GenerationOutcome(
                ok=True,
                spec=replace(spec, prompt_version=prompt_version),
                solid=solid,
                warnings=list(result.warnings),
                repair_attempts=attempt,
                validation_summary=result.summary(),
            )
        except Exception as exc:  # ValidationError, KeyError, SandboxRejection, PipelineError, ...
            last_error = f"{type(exc).__name__}: {exc}"
            errors.append(last_error)

    # Repairs exhausted (SPEC 3.2 Step 5): surface the issue, do NOT export.
    return GenerationOutcome(
        ok=False,
        spec=None,
        solid=None,
        errors=errors,
        repair_attempts=max_repairs,
        validation_summary="repairs exhausted",
    )


def _build(spec: Specification, ops: GeometryOps, allow_freeform: bool) -> tuple[Specification, Any]:
    """Build the solid; return the (possibly normalised) spec and the solid."""
    if spec.mode == "freeform":
        if not allow_freeform:
            raise PipelineError("freeform mode is disabled for this request")
        if not spec.code:
            raise SandboxRejection("empty freeform code")
        return spec, ops.build_freeform(spec.code)
    if not spec.part_type:
        raise PipelineError("template response is missing a part_type")
    from texttocad.geometry import schemas

    part_type = spec.part_type
    validated = schemas.validate_parameters(part_type, spec.parameters)
    # Store the normalised parameters so the spec matches exactly what was built.
    norm = replace(spec, parameters=validated.model_dump(exclude_none=True))
    return norm, ops.build_template(part_type, norm.parameters)
