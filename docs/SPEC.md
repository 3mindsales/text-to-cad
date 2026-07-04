# AI-READY TECHNICAL SPECIFICATION — LOCAL TEXT-TO-CAD ENGINE (PYTHON 3.11)

TARGET PLATFORM: Windows 10/11 (64-bit), air-gapped (no internet required after installation)
DISTRIBUTION: Single-folder bundle via PyInstaller + a separately side-loaded model pack (see Section 11)
DOMAIN SCOPE (MVP): Discrete parametric fabrication parts — brackets, base plates, gussets, flanges, RHS/SHS frames, plates with hole patterns, simple tanks/enclosures and ducts. NOT full assemblies, NOT buildings (that is the IFC/BIM track and stays separate).

---

## 1. SYSTEM OVERVIEW

Build a standalone Windows desktop application that turns a natural-language description plus explicit measurements into a precise, editable, exportable CAD solid.

Primary flow (the "prompt → draft → correct → model" loop):
- User types a description and dimensions (e.g. "steel L-bracket, 150 x 80 x 6 mm, four M8 holes, 8 mm corner fillets").
- A LOCAL LLM converts intent into a validated parametric specification (never raw geometry).
- A deterministic geometry kernel (CadQuery on OpenCASCADE) builds a real B-rep solid from that specification.
- The solid is validated (watertight, non-null, positive volume) and rendered in an interactive viewer.
- The user corrects in natural language ("make it 8 mm thick", "add 2 mm fillets on the inner edges") or by editing exposed parameters directly; the model rebuilds.
- The user exports CAD-grade and fabrication outputs (STEP, DXF, STL, GLB, dimensioned drawing, cut list, report).

Hard rules:
- All processing is 100% local. No cloud services, no telemetry, by default.
- The LLM is bundled and runs offline via Ollama. External LLM providers are an OPT-IN plug-in only (Section 4.4), never the default.
- The LLM never outputs vertices, meshes, or STEP text. It outputs either (a) a JSON parameter object conforming to a fixed schema, or (b) sandboxed CadQuery Python. The kernel is the single source of geometric truth.

Two output classes, kept strictly separate (this is the single most important architectural rule, learned from the mesh-vs-parametric split in the CAD market):
- PARAMETRIC B-REP (STEP/DXF): dimensionally exact, editable, manufacturable. This is the core product.
- TESSELLATED MESH (STL/GLB): derived FROM the B-rep for visualisation, 3D print, and AR only. Never the source of truth.

---

## 2. TECHNOLOGY STACK (EXACT VERSIONS)

| Component | Version | Source |
| --- | --- | --- |
| Python | 3.11.x (64-bit) | python.org |
| Geometry DSL | cadquery 2.4.0+ | pip install cadquery |
| Geometry kernel binding | cadquery-ocp 7.7.x (OpenCASCADE 7.7) | pulled in by cadquery |
| Parameter validation | pydantic 2.6.0+ | pip install pydantic |
| Local LLM runtime | Ollama 0.5.x (bundled ollama.exe) | ollama.com (side-loaded, see 11) |
| LLM client | ollama 0.3.0+ (python client) | pip install ollama |
| In-process LLM fallback | llama-cpp-python 0.3.x | pip install llama-cpp-python |
| UI Framework | PySide6 6.6.0+ | pip install pyside6 |
| 3D Viewer | vtk 9.3.0+ + pyvistaqt 0.11+ | pip install pyvista pyvistaqt |
| DXF I/O | ezdxf 1.1.0+ | pip install ezdxf |
| Mesh/GLB | trimesh 4.1.0+ | pip install trimesh |
| Drawing/PDF | reportlab 4.1.0+ | pip install reportlab |
| Numerics | numpy 1.26.x | pip install numpy |
| Distribution | PyInstaller 6.5.0+ | pip install pyinstaller |
| Cryptography | cryptography 42.0.0+ | pip install cryptography |
| Hardware ID | machineid 0.3.0+ | pip install machineid |

CRITICAL WARNING: Use Python 3.11 exactly. cadquery-ocp wheels are compiled per-Python-version; 3.11 has stable, tested wheels on Windows. Do not use 3.12+ without first confirming an OCP wheel exists for it.

CRITICAL WARNING: cadquery and its OCP dependency are large (600 MB+ once expanded) and pull compiled OpenCASCADE binaries. Install into a clean venv and freeze exact transitive versions in requirements.txt.

Default local model: qwen2.5-coder:7b-instruct (Q4_K_M). Rationale: strong Python/code generation, ~4.7 GB, runs on CPU or 6 GB+ VRAM. Hardware tiers in Section 4.2.

---

## 3. CORE IP: LLM-TO-GEOMETRY PIPELINE (CONSTRAINED GENERATION + VALIDATION + REPAIR)

This section is the product. It is the equivalent of the filtering/cropping logic in a BIM tool: a deterministic, testable boundary around an unreliable input.

### 3.1 Two generation modes (Template default, Freeform advanced)

TEMPLATE MODE (default, reliable):
The LLM does NOT write code. It classifies the request into one of the known Part Types (Section 5.4) and emits a JSON object conforming to that part's pydantic schema. A hand-written, deterministic builder function turns the validated schema into CadQuery calls. Because the geometry code is fixed and only the parameters vary, output is highly reliable and every result is manufacturable.

FREEFORM MODE (advanced toggle, powerful but gated):
For shapes with no matching template, the LLM writes CadQuery Python. This code is AST-validated, executed in a sandbox (Section 4.5), and subjected to the same geometry validation. Freeform is disabled by default and exposed behind an "Advanced: freeform geometry" toggle, mirroring the Manual-XYZ advanced toggle pattern in a BIM crop tool.

### 3.2 The generation pipeline (per request)

- Step 1 — INTENT PARSE. Send the user prompt + the Part-Type catalogue + few-shot examples to the LLM. Require a JSON response: `{"mode": "template"|"freeform", "part_type": "<id or null>", "parameters": {...}}` or `{"mode":"freeform","code":"<cadquery python>"}`.
- Step 2 — SCHEMA VALIDATION. In template mode, validate parameters against the pydantic model for that part_type. Reject out-of-range values (negative thickness, hole diameter larger than plate, etc.) with a structured error. In freeform mode, AST-whitelist the code (Section 4.5).
- Step 3 — BUILD. Execute the builder (template) or the sandboxed code (freeform) to produce a CadQuery Workplane / Solid.
- Step 4 — GEOMETRY VALIDATION (Section 5.5). Confirm the result is a single valid solid: `result.val().isValid()` is True, volume > 0, no free/degenerate faces, bounding box within sane limits. Run manufacturability checks (min wall thickness, minimum hole edge distance) as WARNINGS, not hard failures.
- Step 5 — SELF-REPAIR LOOP. If Step 2, 3, or 4 fails, feed the exact error text back to the LLM with the original request and ask for a corrected specification. Retry up to LLM_MAX_REPAIRS (default 3). Log every attempt. If still failing, surface a clear message and the best partial result, and DO NOT export.
- Step 6 — RENDER + EXPOSE PARAMETERS. Tessellate for the viewer (Section 7) and expose the validated parameters as editable fields/sliders.

### 3.3 Correction loop (edit after first draft)

Natural-language edits are treated as a DIFF against the current validated specification, not a fresh generation:
- Send the current parameters + the edit instruction to the LLM. Require it to return ONLY the changed keys (a JSON patch), or in freeform mode a unified description of the change to apply.
- Merge, re-validate, rebuild, re-validate geometry, re-render.
- Maintain a linear history stack of validated specifications for unlimited Undo/Redo. Each history entry stores the full parameter object + a hash, never a binary model.
- Direct parameter edits (slider/field) bypass the LLM entirely and rebuild instantly.

### 3.4 Determinism guarantee

Given the same validated specification, the builder MUST produce byte-identical STEP output (fixed tessellation tolerance, fixed OCC settings, no randomness). The LLM introduces variance ONLY at the specification stage; everything downstream is deterministic and reproducible. This is what makes the tool trustworthy for engineering use.

---

## 4. LOCAL LLM SUBSYSTEM (BUNDLED OLLAMA + PLUGGABLE BACKENDS)

### 4.1 Runtime architecture

Primary runtime: bundled Ollama. Ollama runs as a local HTTP server on 127.0.0.1:11434. The app talks to it via the ollama python client (or plain HTTP). On startup the app:
- Checks whether the bundled ollama.exe is already running; if not, launches it as a detached subprocess with OLLAMA_MODELS pointed at the bundled model directory (Section 11.2) and OLLAMA_HOST=127.0.0.1:11434.
- Waits for /api/tags to respond, confirms the required model tag is present, and only then unlocks generation.
- If the model tag is missing (air-gapped, nothing to pull), shows: "Model pack not installed — run install_models.bat or select a model folder."

In-process fallback runtime: llama-cpp-python. If Ollama cannot start (locked-down machine, no service rights), the app can load a bundled .gguf directly in-process via llama-cpp-python. Slower to integrate but needs no external process. Selectable in Settings.

### 4.2 Model tiers (target most machines are hardware-constrained)

Assume the typical deployment machine is a modest office/shop-floor PC with little or no discrete GPU. The default must run acceptably there, and there must be an escape hatch to a strong model that needs no local hardware at all (Ollama Cloud). Model choice is a Settings value; the app must NEVER assume a model is present — always query /api/tags first and degrade gracefully.

LOCAL — OFFLINE GGUF via Ollama (air-gapped-safe):
- CONSTRAINED-LOCAL — qwen2.5-coder:3b-instruct (Q4_K_M, ~2 GB) — CPU-only or 4 GB VRAM. For weak machines. Reliability drops on Freeform code; on this tier the app should FORCE Template mode (JSON-schema fill), which a 3B model handles well because it is not writing code, only filling validated parameters. Freeform is disabled at this tier unless the user overrides.
- MINIMUM (DEFAULT) — qwen2.5-coder:7b-instruct (Q4_K_M, ~4.7 GB) — CPU-capable or 6 GB VRAM. The shipped default. Template mode reliable; Freeform usable for simple parts.
- RECOMMENDED — qwen2.5-coder:14b-instruct (Q4_K_M, ~9 GB) — 12 GB+ VRAM. Best local reliability/size trade-off.
- HIGH-LOCAL — qwen2.5-coder:32b-instruct or qwen3-coder:30b — 24 GB+ VRAM. Only for well-equipped workstations.

CLOUD — OLLAMA CLOUD (for constrained machines that need a strong model; NOT air-gapped):
Ollama Cloud lets a weak machine run frontier-scale coding models that would never fit locally (e.g. qwen3-coder:480b-cloud, gpt-oss:120b-cloud) through the EXACT SAME Ollama client and API — the only change is the model tag's `-cloud` suffix. Two access paths, both supported:
- Passthrough via the local daemon: the bundled/installed Ollama server proxies `*-cloud` requests to ollama.com after the user runs `ollama signin` (or the app sets OLLAMA_API_KEY). Same 127.0.0.1:11434 endpoint, same request shape — the daemon forwards it.
- Direct API: point the client host at https://ollama.com with an `Authorization: Bearer $OLLAMA_API_KEY` header (also available on the OpenAI-compatible `/v1/` surface, so the OpenAICompatibleBackend in 4.4 can target it too).

CLOUD TIER — DEFAULT PICK: qwen3-coder:480b-cloud for Freeform/complex parts; a smaller cloud tag for routine Template calls. Auth: `ollama signin` (interactive, opens a browser once) or OLLAMA_API_KEY (headless). Pricing is subscription with usage windows, not per-token. Note: independent reports flagged cloud reliability wobbles (timeouts/empty responses) in early 2026 — implement a timeout + one automatic retry, then fall back to the local model with a visible notice.

ROUTING POLICY (constrained-machine strategy — implement this):
1. Default to the best LOCAL model that fits the detected hardware (probe VRAM/RAM at first run; pick 3b/7b/14b accordingly).
2. Do the heavy lifting with TEMPLATE MODE so even a 3B local model is reliable. Reserve Freeform for genuinely novel shapes.
3. Offer OLLAMA CLOUD as an opt-in "Boost" toggle for when a weak machine hits a request the local model fails (Freeform, complex parts). A cloud model is treated as NON-LOCAL: is_local = False, the "ONLINE LLM ACTIVE" badge shows, and the user must have accepted the external-provider warning. Hybrid is allowed and encouraged: Template calls stay local, Freeform calls route to cloud.
4. In a strict air-gapped deployment, cloud is hard-disabled (see 9.5) so no `-cloud` tag can ever resolve.

CRITICAL: any model tag ending in `-cloud`, and any client host that is not localhost/127.0.0.1/a private IP, MUST be classified NON-LOCAL by the backend, regardless of the fact that it goes through the familiar Ollama client. "It's still Ollama" does not make it air-gapped.

### 4.3 Backend abstraction (this is what makes "other LLMs plug in")

Define an abstract interface. Every provider implements it. The rest of the app depends ONLY on this interface, never on a concrete provider.

```python
class LLMBackend(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...
    @abstractmethod
    def generate_json(self, system: str, user: str,
                      schema_hint: dict | None) -> dict: ...
    @abstractmethod
    def generate_text(self, system: str, user: str) -> str: ...
    @property
    @abstractmethod
    def is_local(self) -> bool: ...   # True => air-gapped-safe
```

Backend selection is config-driven (Section 4.6). Default = OllamaBackend. Any non-local backend is refused unless the user has explicitly enabled "Allow external LLM providers" in Settings AND confirmed a warning dialog. When any non-local backend is active, the title bar shows a persistent "ONLINE LLM ACTIVE" badge.

### 4.4 Provider adapters to implement

- OllamaBackend (default). Talks to 127.0.0.1:11434 (or a configured host). is_local is computed at runtime, NOT hard-coded: it returns False if the active model tag ends in `-cloud` OR the host is not localhost/127.0.0.1/a private IP; otherwise True. This one adapter therefore serves both offline-local models and Ollama Cloud models. Handles cloud auth via `ollama signin` state or OLLAMA_API_KEY.
- LlamaCppBackend (local, in-process gguf). is_local = True.
- OpenAICompatibleBackend (configurable base_url). Covers OpenAI, LM Studio, vLLM, llama.cpp server, Groq, Together, OpenRouter, and any OpenAI-schema endpoint. is_local = True ONLY if base_url resolves to localhost/127.0.0.1/a private IP; otherwise False.
- AnthropicBackend (Messages API). is_local = False.

Each non-local adapter reads its API key from an OS-keyring entry or an env var, NEVER from a plaintext config committed to disk. Keys are never logged.

### 4.5 Sandbox for freeform code (SECURITY-CRITICAL)

LLM-authored CadQuery code is untrusted. Before execution:
- AST WHITELIST: parse with ast, walk the tree, and REJECT any Import/ImportFrom except `cadquery`, `math`, `numpy`; reject Call to eval/exec/compile/__import__/open/getattr/setattr; reject any Attribute access on names `os`, `sys`, `subprocess`, `socket`, `shutil`, `pathlib`, `builtins`, dunder attributes (`__globals__`, `__class__`, etc.).
- EXECUTION ISOLATION: run the validated code in a separate subprocess (not just restricted globals — a subprocess is the real boundary) with a hard wall-clock timeout (LLM_CODE_TIMEOUT, default 15 s) and a memory cap. The subprocess has no network and no working-directory write access except a single temp file for the resulting BREP/STEP handed back to the parent.
- OUTPUT CONTRACT: the subprocess must assign the result to a variable named `result`; the parent reads only that. Anything else is discarded.

If any check fails, treat it as a Step-2 failure and route into the self-repair loop (Section 3.2, Step 5).

### 4.6 Prompt architecture

System prompt (fixed, versioned, shipped with the app) contains: the role, the strict output contract (JSON only, no prose, no markdown fences), the unit convention (mm), the Part-Type catalogue with each schema, and 4–8 few-shot examples spanning the supported part types. Store as a versioned template file; do not hand-build strings inline. Log the prompt VERSION (not the full text) in the report so results are reproducible across app updates.

---

## 5. GEOMETRY ENGINE AND EXPECTATIONS

### 5.1 Units and coordinate system
- Internal working unit: MILLIMETRE. All schemas, all builder math, all STEP output in mm.
- Coordinate system: Z-up, right-handed (CadQuery/OCC native). Part origin at a defined datum per part type (documented per schema).
- User-facing units: mm default; allow a display toggle to inch, but store and export in mm and convert only at the UI edge.

### 5.2 Tessellation tolerance (fixed for determinism)
- Linear deflection: 0.1 mm. Angular deflection: 0.5 rad. Used for the viewer and for STL/GLB. STEP is exact B-rep and unaffected by tessellation.

### 5.3 Supported geometry operations (CadQuery / OCP)
Sketching on workplanes; extrude, revolve, sweep, loft; fillet and chamfer on selected edges; simple, counterbore, and countersunk holes; cosmetic tapped holes (M-series callout stored as metadata, not modelled thread); shell/hollow to a wall thickness; boolean union/cut/intersect; mirror; rectangular and polar patterns; face/edge selection via CadQuery selectors. Anything outside this set is Freeform-mode only.

### 5.4 Part-Type library (Template mode) — the concrete, bounded scope

Each part type is a pydantic model + a deterministic builder. Ship at least these six for the MVP. Each schema below is indicative; enforce ranges and cross-field checks.

- FLAT_PLATE: length, width, thickness; optional edge fillet radius; hole pattern (grid or linear): hole_dia, rows, cols, pitch_x, pitch_y, edge_margin.
- L_BRACKET: leg_a_length, leg_b_length, width, thickness, inner_fillet, holes per leg (dia, count, positions).
- BASE_PLATE: length, width, thickness, corner_holes (dia, edge_margin), optional central bore.
- GUSSET: two edge lengths, thickness, hypotenuse type (straight/curved), optional radius, bolt holes.
- FLANGE: outer_dia, inner_bore_dia, thickness, bolt_circle_dia, bolt_count, bolt_hole_dia.
- BOX_ENCLOSURE / TANK: length, width, height, wall_thickness, open_top (bool), optional lid, optional drain hole.

Cross-field validation examples (reject, don't clamp silently):
- thickness > 0 and thickness < min(length, width)
- hole_dia + 2*edge_margin <= min plate dimension for that pattern
- bolt_hole positions must fall inside the flange annulus
- wall_thickness*2 < min(length, width, height) for a hollow box

### 5.5 Geometry validation gate (every build must pass)
- `result.val().isValid()` is True (OCC BRepCheck).
- Volume > 0 and finite.
- Exactly one solid unless the part type declares multi-solid.
- Bounding box within MAX_PART_ENVELOPE (default 5 m per axis) — a guard against runaway LLM values.
- WARN (not fail) on: min detected wall thickness below MIN_WALL (default 1.5 mm), holes closer to an edge than MIN_EDGE_DISTANCE (default 1.5x dia). Warnings surface in the UI and the report.

---

## 6. DATAFLOW AND EXECUTION ARCHITECTURE

### 6.1 Threading
- The UI runs on the main Qt thread and must never block.
- LLM calls, code execution, geometry building, tessellation, and export all run on a QThread worker. Communicate via signals: status_signal(str), progress_signal(int), result_signal(SpecAndShape), warning_signal(list), error_signal(str).
- Long operations must emit a heartbeat at least every 2 seconds so the UI proves it is alive.

### 6.2 State management
- SINGLE SOURCE OF TRUTH is the current validated specification (parameters or freeform code + part_type + prompt_version). Everything else (solid, mesh, drawing) is derived and cached.
- History stack of specifications for Undo/Redo. Cap at 100 entries; store specs, never binaries.
- The built solid is cached in memory; re-tessellation for the viewer is lazy and cancellable.

### 6.3 Cancellation
- Any in-flight generation/build is cancellable. The worker checks a cancel flag between pipeline steps and terminates the sandbox subprocess on cancel. No temp-file corruption on cancel.

---

## 7. RENDERING AND VIEWER

### 7.1 Viewer
- Embed a VTK render window via pyvistaqt QtInteractor inside the PySide6 layout.
- Tessellate the current solid with `result.val().tessellate(0.1)` -> build a vtkPolyData -> display shaded with edges. Provide orbit/pan/zoom, fit-to-view, and a view cube (front/top/right/iso).
- Colour by validation state: normal solid in neutral grey (#CCCCCC); faces/edges flagged by a warning highlighted in amber (#F5A623); selected feature in the accent blue.

### 7.2 On-model dimensions (MVP-light)
- Show the overall bounding-box dimensions (L x W x H) as an overlay. Full associative dimensioning is Phase 2; the authoritative dimensions live in the parameter panel and the exported drawing.

### 7.3 Parameter panel
- Render the current specification as editable fields grouped by the schema. Numeric fields get a slider + spin-box; ranges come from the pydantic model. Editing a field rebuilds instantly (no LLM). An "Ask AI to change..." text box routes edits through the correction loop (Section 3.3).

---

## 8. EXPORT AND FABRICATION OUTPUT

### 8.1 CAD-grade
- STEP (AP214): `cq.exporters.export(result, "out.step")`. Exact B-rep, mm. This is the primary deliverable.
- DXF (2D): for flat/plate parts, export the true-shape outline + holes via `cq.exporters.export(section, "out.dxf")` or ezdxf from the projected profile. For laser/plasma/waterjet.

### 8.2 Visual / AR (derived, never source of truth)
- STL: `cq.exporters.export(result, "out.stl")` at the fixed tolerance, for 3D print.
- GLB: tessellate -> trimesh -> export .glb (optionally Draco-compressed via an external gltf tool if bundled). Y-up conversion applied on export for ARKit parity, matching the AR pipeline convention in the IFC suite.

### 8.3 Fabrication drawing (Phase 1: basic; Phase 2: full)
- Phase 1: generate three orthographic views (front/top/right) using OCC hidden-line removal (HLR), place them in an A4/A3 titleblock template, annotate overall dimensions and a hole schedule, export to PDF (reportlab) and DXF (ezdxf).
- Phase 2: associative, per-feature dimensioning and tolerancing.

### 8.4 Cut list / takeoff (the local-market edge)
- For a part or a small set: bounding stock size, cut length (for profile/RHS parts), face area, mass = volume x material_density (user picks material: mild steel 7850, aluminium 2700, stainless 8000 kg/m3). Output as CSV and as a section in the report.

### 8.5 Report (conversion_report.txt, per session)
Timestamp; app + prompt-template version; active LLM backend + model + is_local flag; the user prompt; final validated specification (parameters or code hash); part_type; number of repair attempts; geometry validation result; warnings; exported files with sizes; elapsed time per stage (LLM, build, tessellate, export).

---

## 9. AIR-GAPPED SECURITY AND LICENSING

Reuse the licensing model from the IFC suite verbatim in intent; summarised here for completeness.

- 9.1 Machine hash: `machineid.id()` shown in a copyable box in the activation window.
- 9.2 RSA license: 4096-bit public key hard-coded in the .exe; license.key JSON `{machine_hash, expiry, signature}`; verify PKCS1v15 signature, machine match, and expiry before unlocking.
- 9.3 Clock-rollback protection: store last-validation UTC in the Windows Registry on activation; on startup, if system time < stored time, lock with "System clock tampered — license revoked". Optional NTP cross-check (pool.ntp.org) is skipped cleanly when air-gapped.
- 9.4 Anti-debug/obfuscation: PyInstaller bytecode key; --strip; --noupx; obfuscate the licensing + hashing modules; no logic-revealing print()/stack traces to the user.
- 9.5 The LLM subsystem must respect air-gap: with a LOCAL model, assert that no outbound socket is opened beyond 127.0.0.1. Non-local backends — including any Ollama `-cloud` model — are the ONLY code paths allowed to open external sockets, and only after explicit opt-in (Section 4.3). In a strict air-gapped build, cloud must be impossible, not merely un-selected: run Ollama in local-only mode (disable cloud features / do not ship signin credentials or OLLAMA_API_KEY), and have the backend refuse any `-cloud` tag outright. A deployment flag AIRGAP_STRICT=1 hides the cloud "Boost" toggle entirely and blocks the external-provider opt-in.

---

## 10. UI SPECIFICATION — LIGHT MODE PROFESSIONAL

### 10.1 Palette (reuse house style)
Accent #3455FA; background #FFFFFF; text #000000; secondary #555555; borders #E0E0E0; success/progress #34A853; warning #F5A623; error #EA4335. Use Qt-Material light theme, invert_secondary=True.

### 10.2 Layout
- Window 1 — License Activation (modal): machine-hash box, instruction, Browse for license.key, Activate.
- Window 2 — Main Application:
  - Top bar: title + version; LLM status pill (model name; green = local, red "ONLINE LLM ACTIVE" = external).
  - Left panel: the prompt box ("Describe the part and its dimensions"), a Part-Type hint dropdown (Auto / specific), the "Advanced: freeform geometry" toggle, and after generation the editable Parameter panel with sliders.
  - Centre panel: the VTK 3D viewer + view cube + bounding-dimension overlay + a warnings strip.
  - Right panel (collapsible): correction chat ("Ask AI to change...") and the Undo/Redo history list.
  - Bottom bar: Material selector (for mass/cut list), Output-folder selector, Export buttons (STEP / DXF / STL / GLB / Drawing PDF / Cut list CSV), Open Report.

---

## 11. DISTRIBUTION AND COMPILATION

### 11.1 App bundle
PyInstaller one-folder build. cadquery/OCP need care:
- Collect all of cadquery, OCP, vtk, ezdxf data files (use `--collect-all cadquery --collect-all OCP --collect-all vtkmodules` or equivalent hooks).
- Hidden imports for cadquery.occ_impl, OCP submodules used lazily, and vtkmodules.all.
- Test on a clean Windows VM with no Python installed; deliver a signed test report with screenshots.

Indicative command:
```
pyinstaller --onedir --name "TextToCAD" --collect-all cadquery --collect-all OCP --collect-all vtkmodules --collect-all pyvista --add-data "bin;bin" --add-data "prompts;prompts" --strip --noupx main.spec
```

### 11.2 Model pack (the air-gapped reality — READ THIS)
The default 7B model is ~4.7 GB; you cannot ship it inside the PyInstaller onefile, and pulling from the internet violates the air-gap. Ship it as a SEPARATE side-loaded pack:
- Bundle ollama.exe in ./bin/.
- Provide a model pack (the Ollama blob files for the chosen model) delivered on the same media (USB/installer).
- install_models.bat copies the blobs into a local models directory and the app sets OLLAMA_MODELS to it. No download occurs.
- On first run, if the model tag is absent, the app guides the user to run install_models.bat or point at the model folder.
Document total on-disk footprint honestly in the build guide (app + OCC + one model ≈ 6-7 GB minimum; 14B ≈ 11-12 GB).

### 11.3 Build guide deliverable
Exact Python 3.11.x link; venv setup; `pip install -r requirements.txt` with frozen versions; the PyInstaller command and .spec customisations; how to assemble and install the model pack offline; optional code-signing instructions.

---

## 12. ERROR HANDLING — MUST COVER THESE SCENARIOS

- S1 — Ollama not running / model missing: attempt to launch bundled ollama.exe; if still unavailable, show the model-pack guidance and keep the UI usable (viewer + import of existing STEP), block generation only.
- S2 — LLM returns invalid JSON or non-conforming schema: route into the self-repair loop (up to LLM_MAX_REPAIRS); if exhausted, show the raw issue and offer to edit parameters manually.
- S3 — Freeform code fails AST whitelist or sandbox timeout: reject, log, self-repair; never execute unvalidated code.
- S4 — Geometry invalid (isValid False / zero volume / self-intersection): self-repair with the OCC error text; if unresolved, show the last valid model and refuse export of the invalid one.
- S5 — Values out of sane envelope (e.g. 50 m plate): reject at schema validation with a clear range message; do not build.
- S6 — Export target folder not writable: error dialog, ask for another folder, do not export until valid.
- S7 — Out-of-memory during build/tessellation on a huge freeform result: cap envelope + tolerance; catch, abort that build, keep the app alive.
- S8 — User closes app mid-generation: confirm dialog; terminate the worker + sandbox subprocess gracefully; clean temp files.
- S9 — GPU/VTK init failure: fall back to CPU software rendering for the viewer; log a warning; never crash the app over rendering.

---

## 13. DEVELOPER DELIVERABLES

- 13.1 Clean Python source with docstrings on every public function; requirements.txt with exact frozen versions; PyInstaller hooks/ folder.
- 13.2 The full Part-Type library (>=6 types) with pydantic schemas, deterministic builders, and unit tests proving each builds a valid solid across its parameter range.
- 13.3 The LLMBackend interface plus all four adapters (Ollama, llama-cpp, OpenAI-compatible, Anthropic) with the local/non-local gating and the opt-in flow.
- 13.4 The sandbox executor with its AST-whitelist test suite (must reject a documented set of malicious snippets).
- 13.5 Bundled ollama.exe + a documented model-pack assembly + install_models.bat.
- 13.6 A signed clean-VM test report with screenshots.
- 13.7 The Windows build guide (Section 11.3).

Acceptance test: on a clean, offline Windows VM, "L-bracket 150 x 80 x 6 mm, four M8 holes, 8 mm inner fillet" must produce a valid STEP file, a rendered model, and a cut-list CSV, with zero network activity, using only the bundled model.

---

## 14. FINAL NOTES FOR THE DEVELOPER

- The LLM proposes; the kernel disposes. Never let LLM output reach STEP without passing schema validation AND geometry validation. The whole product's credibility rests on this boundary.
- Template mode is the default and should cover the great majority of demo requests reliably. Freeform is a power feature; keep it gated and sandboxed.
- Keep the specification (parameters/code) as the single source of truth. Never store or diff binary models. This makes Undo/Redo, reproducibility, and version control trivial.
- Do not attempt full associative dimensioned drawings or sheet-metal unfolding in Phase 1. Ship overall-dimension drawings + cut lists first; unfold and full GD&T are Phase 2.
- Bundle honesty: state the real disk footprint. A 6-7 GB installer is fine for an on-prem/air-gapped fabrication tool; do not pretend it fits in a small download.
- Air-gap is a selling point for on-prem clients wary of connectivity and data leaving the shop floor. Make "100% offline, your designs never leave this machine" a first-class, visible promise — and enforce it in code, not just in marketing.
