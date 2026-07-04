"""Main application window (SPEC 10.2) — assembles panels, viewer, and the worker.

Wires the prompt -> draft -> correct -> export loop on top of the pipeline. Heavy work
runs on a PipelineWorker (SPEC 6.1). The LLM status pill is green for a local backend and
red ("ONLINE LLM ACTIVE") for any non-local backend (I4).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from texttocad import config
from texttocad.ui.panels import CorrectionPanel, ExportBar, ParameterPanel, PromptPanel
from texttocad.ui.viewer import Viewer
from texttocad.ui.worker import PipelineWorker, run_generation_job

logger = logging.getLogger("texttocad.ui")


class MainWindow(QMainWindow):
    def __init__(self, backend: Any, settings: config.Settings, hardware: config.HardwareInfo) -> None:
        super().__init__()
        self.backend = backend
        self.settings = settings
        self.hardware = hardware

        from texttocad.pipeline.state import SpecHistory

        self.history = SpecHistory()
        self.current_solid: Any = None
        self.current_spec: Any = None
        self._worker: PipelineWorker | None = None

        self.setWindowTitle(f"{config.APP_NAME} {config.APP_VERSION}")
        self.resize(1280, 860)
        self._build_ui()
        self._apply_theme()
        self._update_status_pill()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        self.prompt_panel = PromptPanel()
        self.param_panel = ParameterPanel()
        self.viewer = Viewer()
        self.correction_panel = CorrectionPanel()
        self.export_bar = ExportBar()
        self.warnings_strip = QLabel("")
        self.warnings_strip.setStyleSheet("color: #F5A623; padding: 2px 8px;")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.prompt_panel)
        left_layout.addWidget(self.param_panel)

        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        centre_layout.addWidget(self.viewer)
        centre_layout.addWidget(self.warnings_strip)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(centre)
        splitter.addWidget(self.correction_panel)
        splitter.setSizes([340, 620, 320])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(splitter)
        root_layout.addWidget(self.export_bar)
        self.setCentralWidget(root)

        self.status: QStatusBar = self.statusBar()
        self.pill = QLabel("")
        self.status.addPermanentWidget(self.pill)

        # Wiring
        self.prompt_panel.generateRequested.connect(self._on_generate)
        self.param_panel.paramsChanged.connect(self._on_direct_edit)
        self.correction_panel.correctRequested.connect(self._on_correct)
        self.export_bar.exportRequested.connect(self._on_export)
        self.export_bar.materialChanged.connect(self._on_material)

    def _apply_theme(self) -> None:
        # SPEC 10.1 light palette (Qt-Material is optional; fall back to a stylesheet).
        try:
            from qt_material import apply_stylesheet

            apply_stylesheet(self, theme="light_blue.xml", invert_secondary=True)
        except Exception:
            self.setStyleSheet("QMainWindow { background: #FFFFFF; } QLabel { color: #000000; }")

    def _update_status_pill(self) -> None:
        local = bool(getattr(self.backend, "is_local", True))
        model = getattr(self.backend, "model_tag", getattr(self.backend, "name", "llm"))
        if local:
            self.pill.setText(f"  ● {model}  ")
            self.pill.setStyleSheet(
                "color: #FFFFFF; background: #34A853; border-radius: 8px; padding: 2px 8px;"
            )
        else:
            self.pill.setText("  ● ONLINE LLM ACTIVE  ")
            self.pill.setStyleSheet(
                "color: #FFFFFF; background: #EA4335; border-radius: 8px; padding: 2px 8px;"
            )

    # ------------------------------------------------------------------ #
    def _on_generate(self, prompt: str, part_hint: str, freeform: bool) -> None:
        if not prompt:
            return
        self.status.showMessage("Generating...")
        self._worker = PipelineWorker(run_generation_job, prompt, self.backend, allow_freeform=freeform)
        self._worker.result_signal.connect(self._on_outcome)
        self._worker.error_signal.connect(self._on_error)
        self._worker.status_signal.connect(self.status.showMessage)
        self._worker.start()

    def _on_direct_edit(self, updates: dict) -> None:
        # Direct parameter edits bypass the LLM and rebuild instantly (SPEC 3.3).
        if self.current_spec is None:
            return
        from texttocad.pipeline.correct import apply_patch

        outcome = apply_patch(self.current_spec, updates)
        self._on_outcome(outcome, push_history=True)

    def _on_correct(self, instruction: str) -> None:
        if not instruction or self.current_spec is None:
            return
        from texttocad.pipeline.correct import apply_correction

        self.status.showMessage("Applying correction...")
        outcome = apply_correction(self.current_spec, instruction, self.backend)
        self._on_outcome(outcome, push_history=True)
        self.correction_panel.history.addItem(instruction)

    def _on_outcome(self, outcome: Any, push_history: bool = True) -> None:
        if not getattr(outcome, "ok", False):
            self._on_error("; ".join(getattr(outcome, "errors", []) or ["generation failed"]))
            return
        self.current_spec = outcome.spec
        self.current_solid = outcome.solid
        if push_history:
            self.history.push(outcome.spec)
        self.param_panel.set_specification(outcome.spec.parameters)
        self.viewer.show_solid(outcome.solid, warnings=outcome.warnings)
        self.warnings_strip.setText("  •  ".join(outcome.warnings) if outcome.warnings else "")
        self.export_bar.set_enabled(True)
        self.status.showMessage(outcome.validation_summary or "Done")

    def _on_error(self, message: str) -> None:
        self.export_bar.set_enabled(self.current_solid is not None)
        self.status.showMessage(f"Error: {message}")

    def _on_material(self, material: str) -> None:
        self.settings.material = material

    def _on_export(self, fmt: str) -> None:
        if self.current_solid is None or self.current_spec is None:
            return
        out_dir = Path(self.settings.output_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._on_error(f"output folder not writable: {exc}")
            return
        from texttocad.geometry import exporters

        try:
            if fmt == "STEP":
                exporters.export_step(self.current_solid, out_dir / "part.step")
            elif fmt == "STL":
                exporters.export_stl(self.current_solid, out_dir / "part.stl")
            elif fmt == "GLB":
                exporters.export_glb(self.current_solid, out_dir / "part.glb")
            elif fmt == "DXF":
                from texttocad.geometry import schemas

                spec_obj = schemas.validate_parameters(
                    self.current_spec.part_type, self.current_spec.parameters
                )
                exporters.export_dxf(spec_obj, out_dir / "part.dxf")
            elif fmt == "Drawing PDF":
                exporters.drawing_pdf(self.current_solid, out_dir / "part.pdf")
            elif fmt == "Cut list CSV":
                exporters.cut_list_csv(
                    self.current_solid, out_dir / "cutlist.csv", material=self.settings.material
                )
            elif fmt == "Report":
                self._write_report(out_dir)
            self.status.showMessage(f"Exported {fmt} to {out_dir}")
        except Exception as exc:
            self._on_error(f"export failed: {exc}")

    def _write_report(self, out_dir: Path) -> None:
        from texttocad.reporting.report import ReportData, write_report

        data = ReportData(
            user_prompt=self.prompt_panel.prompt.toPlainText().strip(),
            spec=self.current_spec,
            backend_name=getattr(self.backend, "name", "llm"),
            model=getattr(self.backend, "model_tag", ""),
            is_local=bool(getattr(self.backend, "is_local", True)),
            repair_attempts=0,
            validation_summary="see viewer",
        )
        write_report(out_dir / "conversion_report.txt", data)
