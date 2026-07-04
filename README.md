# TextToCAD

> Local, air-gapped **text-to-CAD** engine. Describe a fabrication part in plain
> language plus dimensions; a **local LLM** turns it into a validated parametric
> specification; a deterministic **CadQuery / OpenCASCADE** kernel builds a real
> B-rep solid; export STEP / DXF / STL / GLB, a dimensioned drawing, and a cut list.
> **100% offline by default.**

See [`docs/SPEC.md`](docs/SPEC.md) for the full technical specification — it is the
single source of truth for this project.

## Status

Early build, delivered as a sequence of PRs (see the phase plan). This shell boots
to an empty window and runs a first-run hardware probe; the LLM, geometry, pipeline,
UI, licensing, and packaging land in subsequent phases.

## Non-negotiable invariants

- **I1** The LLM never emits geometry — only a validated JSON parameter object or
  sandboxed CadQuery Python. The kernel is the only source of geometry.
- **I2** The single source of truth is the validated *specification*; the solid,
  mesh, and drawing are derived. Undo/redo and history operate on specs, never binaries.
- **I3** Given the same specification, the builder produces byte-identical STEP output.
- **I4** Air-gapped by default. A model is *local* only if it is an offline GGUF served
  from localhost; any `-cloud` tag or non-local host is non-local and gated.
- **I5** Every LLM output passes schema *and* geometry validation before export.
- **I6** Freeform (LLM-authored) code is AST-whitelisted and run in an isolated subprocess.

## Local development

Requires **Python 3.11 exactly** (cadquery-ocp wheels are per-Python-version).

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate         # Windows
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m texttocad.app        # opens the bare shell window
```

> Note: `cadquery` + `cadquery-ocp` pull compiled OpenCASCADE binaries (600 MB+
> expanded). The first install is large and slow — this is expected.

### Lint, type-check, test

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## License

Proprietary. Air-gapped licensing (RSA + machine hash + clock-rollback protection)
is enforced in the shipped build — see `docs/SPEC.md` §9.
