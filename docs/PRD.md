# Product Requirements Document — TextToCAD

> Derived from [`docs/SPEC.md`](SPEC.md), which remains the single source of truth.
> Where this PRD and the SPEC disagree, the SPEC wins.

## 1. Problem

Small fabrication shops and engineering practices need dimensionally-exact, editable,
manufacturable CAD (STEP/DXF) for discrete metal parts — brackets, plates, gussets,
flanges, frames, enclosures. Existing "AI CAD" tools output meshes (not manufacturable
B-rep) or require cloud connectivity that shop-floor / on-prem clients reject on data-
sovereignty grounds. There is no trustworthy, **fully offline** path from a plain-language
part description to a real B-rep solid with fabrication outputs.

## 2. Target user

- **Primary:** a fabricator / detailer / small-practice engineer on a modest Windows PC
  (often no discrete GPU), air-gapped or connectivity-averse, who knows the part and its
  dimensions and wants STEP + a cut list fast — without learning a parametric CAD package.
- **Secondary:** the shop owner who needs "our designs never leave this machine" as an
  enforceable guarantee, not a marketing line.

## 3. MVP scope (metalwork-first)

Discrete parametric fabrication parts only. **Six MVP part types** (SPEC 5.4):

| Part type | Datum / key parameters |
| --- | --- |
| `FLAT_PLATE` | length, width, thickness, edge fillet, hole pattern (grid/linear) |
| `L_BRACKET` | two legs, width, thickness, inner fillet, holes per leg |
| `BASE_PLATE` | length, width, thickness, corner holes, optional central bore |
| `GUSSET` | two edge lengths, thickness, straight/curved hypotenuse, bolt holes |
| `FLANGE` | outer/bore dia, thickness, bolt circle, bolt count/dia |
| `BOX_ENCLOSURE` / `TANK` | length, width, height, wall thickness, open top, lid, drain |

**Explicit non-goals (v1):** assemblies, buildings/BIM, full associative GD&T dimensioning,
sheet-metal unfolding, generative/organic shapes outside the gated Freeform mode.

## 4. User journeys

### 4.1 First run / licensing
1. App launches → clock-rollback check → **License Activation** modal shows the machine hash.
2. User pastes the vendor-issued `license.key`; RSA signature + machine + expiry verified.
3. On success the main window unlocks. A first-run **hardware probe** recommends a local
   model tier (3b/7b/14b) from detected RAM/VRAM.

### 4.2 Prompt → draft → correct → export (the core loop)
1. User types a description + dimensions ("L-bracket 150×80×6 mm, four M8 holes, 8 mm inner fillet").
2. Local LLM (Template mode) emits a **validated JSON parameter object** (never geometry).
3. Deterministic CadQuery builder produces a B-rep solid; the geometry gate validates it.
4. The solid renders in the 3D viewer; validated parameters appear as editable sliders/fields.
5. User corrects in natural language ("make it 8 mm thick") — treated as a **JSON patch** —
   or edits a parameter directly (instant rebuild, no LLM).
6. User picks a material and exports STEP / DXF / STL / GLB / drawing PDF / cut-list CSV, and
   opens the conversion report.

### 4.3 Constrained-hardware boost
On a weak machine, heavy Template work stays local and reliable. If a Freeform/complex
request exceeds the local model, the user may opt into an **Ollama Cloud "Boost"** — which
flips the app to a visible "ONLINE LLM ACTIVE" state and is impossible in `AIRGAP_STRICT` builds.

## 5. Requirements traceable to invariants

| # | Requirement | Invariant |
| --- | --- | --- |
| R1 | The LLM emits only a validated spec (JSON params) or sandboxed CadQuery code — never geometry. | I1 |
| R2 | The validated specification is the single source of truth; solids/meshes/drawings are derived. Undo/redo operates on specs. | I2 |
| R3 | The same spec yields byte-identical STEP (fixed tolerance/OCC settings, no randomness). | I3 |
| R4 | A model is local only if it is an offline GGUF on localhost; `-cloud`/non-local ⇒ gated + badge. | I4 |
| R5 | Every result passes schema **and** geometry validation before export; failures self-repair. | I5 |
| R6 | Freeform code is AST-whitelisted and run in an isolated, no-network, timeout-bounded subprocess. | I6 |

## 6. Measurable acceptance criteria

- **AC1 (headline):** On a clean, offline Windows VM with only the bundled 7b model, the prompt
  "L-bracket 150 × 80 × 6 mm, four M8 holes, 8 mm inner fillet" produces a **valid STEP file**,
  a **rendered model**, and a **cut-list CSV**, with **zero external sockets opened**.
- **AC2:** Each of the six part types builds a valid solid (`isValid()`, volume > 0, single solid)
  across the low/mid/high of every parameter range.
- **AC3:** Re-exporting the same validated spec yields **byte-identical STEP** twice.
- **AC4:** An out-of-range request (e.g. 50 m plate, negative thickness) is rejected at schema
  validation with a clear message and **does not build**.
- **AC5:** A malicious Freeform snippet (import os, `open()`, `__globals__`, subprocess, socket,
  eval) is rejected by the AST whitelist and never executed.
- **AC6:** Selecting a `-cloud` model or a non-local host sets `is_local() == False`, shows the
  "ONLINE LLM ACTIVE" badge, and is blocked entirely when `AIRGAP_STRICT=1`.
- **AC7:** On the 3b tier, Freeform is forced off and Template mode still satisfies AC1.
- **AC8:** Licensing: a valid license unlocks; wrong machine hash / expired / tampered signature /
  clock rollback all lock the app.

## 7. Success signals

- A fabricator goes from prompt to a manufacturable STEP + cut list in under a minute, offline.
- Zero network egress observable during a local generation (verifiable, not just claimed).
- Reproducible outputs: same spec → same STEP, across app updates (prompt version logged).
