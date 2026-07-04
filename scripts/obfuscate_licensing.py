"""Free licensing obfuscation (no PyArmor) — compile the licensing modules to native `.pyd`.

SPEC 9.4 wants the licensing/hashing modules obfuscated. PyArmor needs a paid licence;
Cython is the free, AV-friendly alternative (ADR-0005): it compiles the pure-Python
modules to native machine code (`.pyd` C extensions), so the shipped bundle carries
compiled licence/clock logic instead of decompilable `.pyc`.

In place (intended for a RELEASE checkout — it removes source):
  1. cythonize machine_id.py / rsa_verify.py / rollback.py -> *.pyd (via MSVC),
  2. delete the .py (and generated .c), leaving __init__.py + the .pyd + public_key.pem,
  3. smoke-import the compiled package so a broken extension fails the build loudly.

Prereqs (build host only): `pip install cython` + MSVC Build Tools. Nothing here ships.

Usage:
    python scripts/obfuscate_licensing.py            # compile + strip sources (release)
    python scripts/obfuscate_licensing.py --keep-sources
    python scripts/obfuscate_licensing.py --check    # verify Cython + a compiler exist
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess  # nosec B404 - runs the local python build of our own setup snippet
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "src", "texttocad", "licensing")
MODULES = ("machine_id", "rsa_verify", "rollback")  # __init__ stays a thin re-export


def _have_cython() -> bool:
    try:
        import Cython  # noqa: F401

        return True
    except ImportError:
        return False


def _have_compiler() -> bool:
    try:
        from setuptools._distutils import ccompiler, errors

        c = ccompiler.new_compiler()
        try:
            c.initialize()  # MSVCCompiler finds VS Build Tools via vswhere
        except (errors.DistutilsPlatformError, AttributeError):
            return False
        return True
    except Exception:
        return False


def _compile() -> None:
    setup_src = (
        "from setuptools import setup\n"
        "from Cython.Build import cythonize\n"
        f"mods = {[os.path.join(PKG, m + '.py') for m in MODULES]!r}\n"
        "setup(ext_modules=cythonize(mods, language_level=3), script_args=['build_ext', '--inplace'])\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix="_setup.py", delete=False, dir=PKG) as fh:
        fh.write(setup_src)
        setup_path = fh.name
    try:
        subprocess.run([sys.executable, setup_path], cwd=PKG, check=True)  # nosec B603
    finally:
        os.remove(setup_path)


def _strip_sources() -> None:
    for m in MODULES:
        for ext in (".py", ".c"):
            p = os.path.join(PKG, m + ext)
            if os.path.exists(p):
                os.remove(p)
    for build_dir in glob.glob(os.path.join(PKG, "build")):
        shutil.rmtree(build_dir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--keep-sources", action="store_true")
    args = ap.parse_args()

    cy, cc = _have_cython(), _have_compiler()
    if args.check:
        print(f"cython: {cy}  compiler: {cc}")
        return 0 if (cy and cc) else 1
    if not (cy and cc):
        print("ERROR: need Cython and a C compiler (MSVC Build Tools).", file=sys.stderr)
        return 1

    _compile()
    if not args.keep_sources:
        _strip_sources()
    # Smoke-import the (now compiled) package.
    src_dir = os.path.join(ROOT, "src")
    subprocess.run(  # nosec B603
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, r'{src_dir}'); import texttocad.licensing",
        ],
        check=True,
    )
    print("licensing modules obfuscated (.pyd)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
