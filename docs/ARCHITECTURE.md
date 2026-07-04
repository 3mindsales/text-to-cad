# Architecture — TextToCAD

> Companion to [`docs/SPEC.md`](SPEC.md). Diagrams are Mermaid; they render on GitHub.

## Overview

TextToCAD is a single-process PySide6 desktop app with a strict internal boundary: an
**unreliable LLM front-half** proposes a *specification*, and a **deterministic geometry
back-half** disposes of it into a real B-rep solid. The specification — not any binary — is
the single source of truth (I2). All processing is local by default (I4).

Layers:

- **`ui/`** — PySide6 windows/panels, VTK viewer, and a QThread worker (main thread never blocks).
- **`pipeline/`** — generate → validate → self-repair, the natural-language correction loop, and
  the specification history stack.
- **`llm/`** — the `LLMBackend` interface, four provider adapters, the tier/hybrid router, and the
  security-critical Freeform sandbox.
- **`geometry/`** — pydantic schemas, deterministic builders, the geometry validation gate, and exporters.
- **`licensing/`** — RSA verification, machine hash, clock-rollback guard.
- **`reporting/`** — the per-session conversion report.

---

## 1. System context

```mermaid
flowchart TB
    user([Fabricator / engineer])
    subgraph app["TextToCAD desktop app (local process)"]
        ui["UI + Viewer"]
        pipe["Pipeline<br/>generate / correct / state"]
        geo["Geometry kernel<br/>CadQuery + OpenCASCADE"]
        llm["LLM subsystem<br/>backends + router + sandbox"]
        lic["Licensing"]
    end
    ollama["Local Ollama daemon<br/>127.0.0.1:11434"]
    cloud["Ollama Cloud / external LLM<br/>(opt-in, non-local)"]
    fs[("Filesystem outputs<br/>STEP / DXF / STL / GLB / PDF / CSV / report")]

    user --> ui
    ui --> pipe
    pipe --> llm
    pipe --> geo
    llm -->|local, air-gapped| ollama
    llm -.->|opt-in only, gated<br/>ONLINE LLM ACTIVE| cloud
    geo --> fs
    lic -->|unlock| ui

    classDef ext fill:#f5a623,stroke:#b37400,color:#000;
    class cloud ext;
```

The dashed edge to Ollama Cloud is the **only** path allowed to open an external socket, and
only after explicit opt-in; it is impossible in an `AIRGAP_STRICT` build (I4, SPEC 9.5).

---

## 2. Generation pipeline (matches SPEC 3.2 exactly)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant P as Pipeline
    participant L as LLM backend
    participant S as Schema / AST validator
    participant B as Builder (CadQuery)
    participant G as Geometry gate
    participant V as Viewer

    U->>P: prompt + dimensions
    loop up to LLM_MAX_REPAIRS (default 3)
        P->>L: Step 1 — intent parse (catalogue + few-shot)
        L-->>P: {mode, part_type, parameters} or {freeform code}
        P->>S: Step 2 — schema validate (template) / AST whitelist (freeform)
        alt invalid
            S-->>P: structured error
            P->>L: Step 5 — self-repair with exact error text
        else valid
            P->>B: Step 3 — build solid
            B-->>P: CadQuery Workplane / Solid (or build error)
            P->>G: Step 4 — geometry gate (isValid, volume>0, single solid, envelope)
            alt gate fails
                G-->>P: OCC error / warning
                P->>L: Step 5 — self-repair
            else gate passes
                G-->>P: valid solid (+ manufacturability warnings)
                P->>V: Step 6 — tessellate 0.1 mm + expose parameters
                Note over P,V: export unlocked
            end
        end
    end
    Note over P: repairs exhausted → show best partial, DO NOT export
```

---

## 3. LLM backend class diagram (interface + adapters + router)

```mermaid
classDiagram
    class LLMBackend {
        <<abstract>>
        +is_available() bool
        +generate_json(system, user, schema_hint) dict
        +generate_text(system, user) str
        +is_local bool
    }
    class OllamaBackend {
        +host: str
        +model_tag: str
        +is_local bool
    }
    class LlamaCppBackend {
        +is_local bool
    }
    class OpenAICompatibleBackend {
        +base_url: str
        +is_local bool
    }
    class AnthropicBackend {
        +is_local bool
    }
    class Router {
        +select(settings, hardware) LLMBackend
        +route(call_kind) LLMBackend
    }

    LLMBackend <|.. OllamaBackend
    LLMBackend <|.. LlamaCppBackend
    LLMBackend <|.. OpenAICompatibleBackend
    LLMBackend <|.. AnthropicBackend
    Router --> LLMBackend : depends only on interface

    note for OllamaBackend "is_local computed at runtime: any -cloud tag or non-local host is non-local, so gated + badge (I4)"
    note for LlamaCppBackend "in-process GGUF, always local"
    note for AnthropicBackend "always non-local"
    note for Router "external/cloud refused unless allow_external_llm AND not AIRGAP_STRICT; Template stays local, Freeform may Boost"
```

---

## 4. State / data-flow — the specification is the source of truth (I2)

```mermaid
flowchart LR
    prompt[/prompt or NL edit/] --> spec{{"Validated Specification<br/>part_type + parameters/code + prompt_version"}}
    spec -->|deterministic build| solid[B-rep solid cache]
    solid -->|tessellate 0.1 mm| mesh[Viewer mesh / STL / GLB]
    solid -->|exact| step[STEP / DXF]
    solid -->|HLR| drawing[Drawing PDF/DXF]
    solid -->|volume x density| cutlist[Cut list CSV]

    spec --> history[["History stack<br/>(specs only, capped 100)"]]
    history -->|undo / redo| spec
    slider[/direct parameter edit/] -->|bypass LLM| spec

    classDef truth fill:#3455fa,stroke:#1a2f9e,color:#fff;
    class spec truth;
```

Everything to the right of the specification is **derived and cached**. Undo/redo, persistence,
and reproducibility operate on specifications; binaries are never stored or diffed.

---

## 5. Deployment view (offline Windows bundle + side-loaded model pack)

```mermaid
flowchart TB
    subgraph media["Delivery media (USB / installer)"]
        bundle["PyInstaller one-folder bundle<br/>TextToCAD.exe + cadquery/OCP/vtk/PySide6"]
        olexe["bin/ollama.exe"]
        pack["Model pack (Ollama blobs, ~4.7 GB for 7b)"]
        installer["install_models.bat"]
    end
    subgraph machine["Air-gapped Windows PC"]
        exe["TextToCAD.exe"]
        models["OLLAMA_MODELS dir"]
        daemon["ollama.exe @ 127.0.0.1:11434"]
        lickey["license.key + public_key.pem"]
    end

    bundle --> exe
    olexe --> daemon
    installer -->|copies blobs, no download| models
    pack --> installer
    exe -->|launch/attach| daemon
    daemon --> models
    lickey -->|verify| exe

    note1["Total on-disk: app + OCC + one model<br/>~6-7 GB (14b ~11-12 GB)"]
```

The bundle ships no cloud credentials in an `AIRGAP_STRICT` variant; the daemon runs local-only
and the backend refuses any `-cloud` tag (SPEC 9.5).
