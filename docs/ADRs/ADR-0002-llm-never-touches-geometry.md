# ADR-0002 — The LLM never touches geometry; the specification is the source of truth

- Status: Accepted
- Date: 2026-07-04

## Context

LLMs are unreliable at emitting valid geometry (vertices, meshes, STEP text). The product's
credibility rests on a deterministic, testable boundary around that unreliable input.

## Decision

The LLM emits **only** (a) a JSON parameter object validated against a pydantic schema
(Template mode) or (b) sandboxed CadQuery Python (Freeform mode) — **never** geometry (I1).
The **validated specification** (part_type + parameters/code + prompt_version) is the single
source of truth; the solid, mesh, and drawing are all derived and cached (I2). Undo/redo,
history, and persistence operate on specifications, never binaries.

## Consequences

- A clean, unit-testable boundary: schema + geometry validation gate every result before export (I5).
- Trivial, reliable Undo/Redo and reproducibility — history stores specs + hashes, not binaries.
- Determinism (I3) follows naturally: same spec → same build → byte-identical STEP.
- Requires disciplined enforcement everywhere: no code path may let raw LLM output reach an
  exporter without passing both validators.
