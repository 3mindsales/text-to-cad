# ADR-0001 — CadQuery + OpenCASCADE as the geometry kernel

- Status: Accepted
- Date: 2026-07-04

## Context

We need dimensionally-exact, manufacturable B-rep geometry (STEP/DXF), produced from a
programmatic specification, fully offline. Options considered: CadQuery (on OpenCASCADE via
`cadquery-ocp`), build123d (also OCC), raw OCC/pythonocc, and mesh-first kernels (trimesh/CGAL).

## Decision

Use **CadQuery 2.4** on **OpenCASCADE 7.7** (`cadquery-ocp`). CadQuery is an LLM-friendly,
code-based DSL that maps cleanly to our deterministic builders; OCC gives exact B-rep, STEP
AP214 export, HLR drawings, and `BRepCheck` validation. Wheels exist for Python 3.11 on Windows
(`cadquery-ocp` cp311 win_amd64 confirmed), which keeps the air-gapped bundle buildable.

## Consequences

- Exact, editable, manufacturable output — the core product promise. Mesh (STL/GLB) is derived
  from the B-rep for visualisation/AR only, never the source of truth.
- Large native footprint (OCC binaries 600 MB+ expanded); accepted for an on-prem tool.
- Determinism (I3) is achievable with fixed OCC/tessellation settings.
- If we ever switch the DSL to build123d, we must update this ADR, SPEC §2/§5, and the geometry
  phase together so docs and code do not diverge.
