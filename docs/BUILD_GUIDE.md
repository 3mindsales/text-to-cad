# TextToCAD — Windows Build Guide (SPEC 11.3)

How to build the offline Windows bundle, assemble the side-loaded model pack, and
produce an air-gapped-strict variant.

## 1. Prerequisites (build host only)

- **Python 3.11.x (64-bit)** — https://www.python.org/downloads/release/python-3119/
  (cadquery-ocp wheels are compiled per Python version; **use 3.11 exactly**).
- Git, and internet access **at build time only** (to fetch wheels). The resulting bundle
  runs fully offline.
- For licensing obfuscation (optional, release): **Cython** + **MSVC Build Tools for Visual
  Studio** (free).

## 2. Set up the environment

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> `cadquery` + `cadquery-ocp` pull compiled OpenCASCADE binaries (600 MB+ expanded). The
> first install is large and slow — expected.

Run the app from source to verify: `set PYTHONPATH=src && python -m texttocad.app`
(use `set TEXTTOCAD_DEV_NO_LICENSE=1` to bypass activation during development).

## 3. Licensing keys (one-time, vendor side)

```bat
python scripts\keygen.py 4096
```
Writes `src\texttocad\licensing\public_key.pem` (bundled) and `_vendor\private_key.pem`
(**keep private, never commit/bundle**). Sign a customer license:
```bat
python scripts\sign_license.py <machine_hash> 2027-12-31 license.key
```

### (Optional, release) obfuscate the licensing modules — SPEC 9.4 / ADR-0005
```bat
python scripts\obfuscate_licensing.py --check      REM verify Cython + compiler
python scripts\obfuscate_licensing.py              REM compile to .pyd, strip .py
```

## 4. Build the one-folder bundle

```bat
scripts\build_windows.bat
```
This creates a clean `.buildvenv`, installs pinned deps + PyInstaller 6.5.0, and runs:
```bat
pyinstaller packaging\texttocad.spec --noconfirm
```
Output: `dist\TextToCAD\TextToCAD.exe` plus the one-folder native bundle.

`.spec` notes: `collect_all` for cadquery/OCP/vtkmodules/pyvista/pyvistaqt/ezdxf/reportlab/
trimesh; hidden imports for `cadquery.occ_impl`, `vtkmodules.all`, cryptography primitives,
`machineid`, and the PySide6 SVG modules; `--strip`, `--noupx`, `console=False` (SPEC 9.4);
bundles `bin/`, `texttocad/llm/prompts`, and `public_key.pem`.

## 5. Bundle the local LLM (side-loaded model pack — SPEC 11.2)

1. Place **`ollama.exe`** in `bin\` (bundled by the spec).
2. Ship the chosen model's Ollama blobs/manifests as a `model_pack\` folder on the media.
3. On the target machine, run:
   ```bat
   scripts\install_models.bat model_pack
   ```
   This copies the blobs into `models\` and sets `OLLAMA_MODELS` — **no download**.
4. On first run, if the model tag is absent the app guides the user to run this script.

## 6. Honest on-disk footprint

| Configuration | Approx. size |
| --- | --- |
| App + OpenCASCADE + **7b** model | **~6–7 GB** |
| App + OpenCASCADE + **14b** model | ~11–12 GB |

A 6–7 GB installer is normal for an on-prem/air-gapped fabrication tool. Do not pretend it
fits in a small download.

## 7. Ollama Cloud "Boost" (NON air-gapped, opt-in)

For a weak machine that needs a strong model on a Freeform/complex request:
- `ollama signin` once (interactive) **or** set `OLLAMA_API_KEY` (headless).
- In Settings, enable **Allow external LLM providers**. A `-cloud` tag or non-local host is
  classified non-local — the title bar shows **"ONLINE LLM ACTIVE"** (invariant I4).

## 8. AIRGAP_STRICT variant (cloud impossible)

Build/deploy with `AIRGAP_STRICT=1` (env or config). Then:
- the external-provider opt-in is blocked and the cloud "Boost" toggle is hidden,
- the backend refuses any `-cloud` tag outright,
- ship **no** signin credentials / `OLLAMA_API_KEY`.

## 9. Code signing (optional)

Sign `TextToCAD.exe` with your Authenticode certificate:
```bat
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 dist\TextToCAD\TextToCAD.exe
```

## 10. Clean-VM test

Test on a clean, offline Windows VM with **no Python installed**. Verify the app launches,
runs a local generation, and exports a valid STEP + cut list with **zero network activity**
(see `docs/TEST_REPORT_TEMPLATE.md`).
