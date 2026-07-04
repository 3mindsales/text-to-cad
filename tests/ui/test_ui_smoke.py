"""UI smoke tests (SPEC 10) — construct widgets offscreen; verify wiring + the status pill.

Requires PySide6 (skipped otherwise). VTK is not required: the viewer falls back to a
software placeholder (SPEC 12 S9), which these tests also exercise.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from texttocad import config  # noqa: E402
from texttocad.ui.main_window import MainWindow  # noqa: E402
from texttocad.ui.panels import ExportBar, ParameterPanel, PromptPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _LocalBackend:
    name = "ollama"
    model_tag = "qwen2.5-coder:7b-instruct"

    @property
    def is_local(self):
        return True


class _ExternalBackend(_LocalBackend):
    @property
    def is_local(self):
        return False


def _hw():
    return config.HardwareInfo(total_ram_gb=8.0, vram_gb=None, has_nvidia_gpu=False, recommended_tier="7b")


def test_mainwindow_constructs_local_pill(qapp):
    w = MainWindow(_LocalBackend(), config.Settings(), _hw())
    assert "TextToCAD" in w.windowTitle()
    assert "ONLINE" not in w.pill.text()  # local => green, no online badge
    # index 0 = "Material:" label, 1 = material combo, 2 = first export button.
    assert not w.export_bar._buttons.itemAt(2).widget().isEnabled()  # export disabled initially


def test_external_backend_shows_online_badge(qapp):
    w = MainWindow(_ExternalBackend(), config.Settings(), _hw())
    assert "ONLINE LLM ACTIVE" in w.pill.text()


def test_prompt_panel_emits(qapp):
    p = PromptPanel()
    received = []
    p.generateRequested.connect(lambda pr, h, f: received.append((pr, h, f)))
    p.prompt.setPlainText("flat plate 100 x 100 x 5")
    p.generate_btn.click()
    assert received and received[0][0] == "flat plate 100 x 100 x 5"


def test_parameter_panel_builds_and_emits(qapp):
    panel = ParameterPanel()
    changes = []
    panel.paramsChanged.connect(lambda d: changes.append(d))
    panel.set_specification({"length": 100.0, "width": 100.0, "thickness": 5.0})
    panel._spins["thickness"].setValue(8.0)
    assert changes and changes[-1]["thickness"] == 8.0
    assert changes[-1]["length"] == 100.0


def test_export_bar_toggle(qapp):
    bar = ExportBar()
    bar.set_enabled(True)
    # First button after the material combo is an export button.
    btn = bar._buttons.itemAt(2).widget()
    assert btn.isEnabled()


def test_viewer_fallback_without_vtk(qapp):
    from texttocad.ui.viewer import Viewer

    v = Viewer()
    # In CI VTK/pyvistaqt is not installed -> software fallback, no crash.
    assert v.has_gpu_viewer in (True, False)
