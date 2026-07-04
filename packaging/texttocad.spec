# PyInstaller one-folder spec for TextToCAD (SPEC 11.1).
#
# Build from the repo root:  pyinstaller packaging/texttocad.spec --noconfirm
# Produces dist/TextToCAD/TextToCAD.exe plus a one-folder bundle of native libraries.
#
# cadquery + OCP + vtk + pyvista pull large compiled OpenCASCADE/VTK binaries; we
# collect-all their data + binaries and add the hidden imports they load lazily.

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(ROOT, "src")

# --- collect heavy packages (datas, binaries, hiddenimports) -----------------
datas, binaries, hiddenimports = [], [], []
for pkg in ("cadquery", "OCP", "vtkmodules", "pyvista", "pyvistaqt", "ezdxf", "reportlab", "trimesh"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("vtkmodules")
hiddenimports += [
    "cadquery.occ_impl",
    "vtkmodules.all",
    "vtkmodules.util.numpy_support",
    "machineid",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.asymmetric.padding",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    "cryptography.exceptions",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
]

# --- app data: bundled binaries, prompts, and the public key -----------------
if os.path.isdir(os.path.join(ROOT, "bin")):
    datas += [(os.path.join(ROOT, "bin"), "bin")]  # ollama.exe etc. (side-loaded)
datas += [(os.path.join(SRC, "texttocad", "llm", "prompts"), "texttocad/llm/prompts")]
datas += [
    (
        os.path.join(SRC, "texttocad", "licensing", "public_key.pem"),
        "texttocad/licensing",
    )
]

a = Analysis(
    [os.path.join(SRC, "texttocad", "app.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(ROOT, "packaging", "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "pytest", "IPython", "Cython"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TextToCAD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # SPEC 9.4
    upx=False,  # SPEC 9.4 (UPX trips antivirus)
    console=False,  # windowed app; no logic-revealing console (SPEC 9.4)
    disable_windowed_traceback=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name="TextToCAD",
)
