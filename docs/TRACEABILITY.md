# Traceability — SPEC section → module/file

Maps each SPEC section to the module(s) that implement it and the phase/PR that delivers it.
A checklist for later phases; "planned" paths are created as their phase lands.

| SPEC § | Concern | Module / file | Phase / PR | Status |
| --- | --- | --- | --- | --- |
| 1 | System overview / core loop | `pipeline/`, `ui/` | 4, 5 | planned |
| 2 | Tech stack / exact versions | `requirements.txt`, `pyproject.toml` | 1 | done |
| 3.1–3.2 | Generation pipeline + self-repair | `pipeline/generate.py` | 4 | planned |
| 3.3 | NL correction loop (JSON patch) | `pipeline/correct.py` | 4 | planned |
| 3.4 | Determinism guarantee | `geometry/builders.py`, `geometry/exporters.py` | 3 | planned |
| 4.1 | Ollama runtime lifecycle | `llm/ollama_backend.py` | 2 | planned |
| 4.2 | Model tiers + hardware probe | `config.py` (probe), `llm/router.py` | 1, 2 | probe done; router planned |
| 4.3 | `LLMBackend` interface | `llm/base.py` | 2 | planned |
| 4.4 | Provider adapters + is_local gating | `llm/{ollama,llamacpp,openai_compat,anthropic}_backend.py` | 2 | planned |
| 4.5 | Freeform sandbox (AST + subprocess) | `llm/sandbox.py` | 2 | planned |
| 4.6 | Versioned prompt architecture | `llm/prompts/` + loader | 2 | planned |
| 5.1 | Units (mm internal, inch display) | `geometry/units.py` | 3 | planned |
| 5.2 | Fixed tessellation tolerance | `config.py` constants, `geometry/exporters.py` | 1, 3 | consts done |
| 5.3 | Supported operations | `geometry/builders.py` | 3 | planned |
| 5.4 | Six part-type schemas | `geometry/schemas.py` | 3 | planned |
| 5.5 | Geometry validation gate | `geometry/validate.py` | 3 | planned |
| 6.1 | Threading / signals | `ui/worker.py` | 5 | planned |
| 6.2 | State / history (specs only) | `pipeline/state.py` | 4 | planned |
| 6.3 | Cancellation | `ui/worker.py`, `llm/sandbox.py` | 5 | planned |
| 7.1 | VTK viewer | `ui/viewer.py` | 5 | planned |
| 7.2 | Bounding-dimension overlay | `ui/viewer.py` | 5 | planned |
| 7.3 | Parameter panel | `ui/panels.py` | 5 | planned |
| 8.1 | STEP / DXF export | `geometry/exporters.py` | 3 | planned |
| 8.2 | STL / GLB (Y-up) | `geometry/exporters.py` | 3 | planned |
| 8.3 | Fabrication drawing (HLR) | `geometry/exporters.py` | 3 | planned |
| 8.4 | Cut list / takeoff | `geometry/exporters.py`, `config.py` densities | 1, 3 | densities done |
| 8.5 | Conversion report | `reporting/report.py` | 4 | planned |
| 9.1–9.3 | Machine hash / RSA / rollback | `licensing/{machine_id,rsa_verify,rollback}.py` | 7 | planned |
| 9.4 | Obfuscation (Cython, per ADR-0005) | `scripts/obfuscate_licensing.py` | 6/7 | planned |
| 9.5 | Air-gap enforcement / AIRGAP_STRICT | `config.py`, `llm/router.py`, `llm/*backend.py` | 1, 2 | config done |
| 10 | UI spec / palette | `ui/main_window.py`, `ui/panels.py`, `ui/activation.py` | 5 | planned |
| 11 | Distribution / model pack | `packaging/texttocad.spec`, `scripts/install_models.bat`, `scripts/build_windows.bat` | 6 | placeholders |
| 12 | Error scenarios S1–S9 | across `pipeline/`, `ui/`, `llm/` + `tests/acceptance/` | 8 | planned |
| 13 | Developer deliverables | whole repo + `tests/` | all | in progress |

## CI/CD (delivered PRs 2–6, beyond the SPEC's dev-deliverables)

| Concern | File | PR |
| --- | --- | --- |
| Lint + format + type | `.github/workflows/lint.yml` | 2 |
| Tests + coverage gate | `.github/workflows/test.yml` | 3 |
| Dependency review + audit + Dependabot | `.github/workflows/dependency-review.yml`, `.github/dependabot.yml` | 4 |
| Secret + static security | `.github/workflows/security.yml`, `.gitleaks.toml` | 5 |
| CodeQL | `.github/workflows/codeql.yml` | 6 |
