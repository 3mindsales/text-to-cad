"""Guard the PyInstaller spec + packaging scripts (SPEC 11).

Cannot run a full PyInstaller build in CI (heavy/flaky); instead assert the spec parses
and carries the security-relevant settings and the required bundled data.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging" / "texttocad.spec"


def test_spec_parses():
    ast.parse(SPEC.read_text(encoding="utf-8"))


def test_spec_security_settings():
    text = SPEC.read_text(encoding="utf-8")
    assert "strip=True" in text  # SPEC 9.4
    assert "upx=False" in text  # SPEC 9.4 (UPX trips AV)
    assert "console=False" in text  # windowed; no logic-revealing console
    # Collects the heavy native packages.
    for pkg in ("cadquery", "OCP", "vtkmodules", "pyvista", "ezdxf", "reportlab"):
        assert pkg in text
    # Bundles the versioned prompts and the public key.
    assert "texttocad/llm/prompts" in text
    assert "public_key.pem" in text


def test_scripts_present():
    for name in (
        "install_models.bat",
        "build_windows.bat",
        "keygen.py",
        "sign_license.py",
        "obfuscate_licensing.py",
    ):
        assert (ROOT / "scripts" / name).exists(), name


def test_build_guide_states_footprint():
    guide = (ROOT / "docs" / "BUILD_GUIDE.md").read_text(encoding="utf-8")
    assert "6" in guide and "GB" in guide  # honest footprint disclosed
    assert "AIRGAP_STRICT" in guide
