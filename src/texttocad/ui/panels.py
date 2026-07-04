"""UI panels (SPEC 7.3, 10.2): prompt, parameter editor, correction chat, export bar.

The parameter panel is generated from the current specification; editing a numeric field
emits ``paramsChanged`` so the main window can rebuild instantly (bypassing the LLM).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from texttocad.config import MATERIAL_DENSITIES, MAX_PART_ENVELOPE_MM
from texttocad.geometry import schemas

EXPORT_FORMATS = ["STEP", "DXF", "STL", "GLB", "Drawing PDF", "Cut list CSV", "Report"]


class PromptPanel(QWidget):
    generateRequested = Signal(str, str, bool)  # prompt, part_hint, freeform

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Describe the part and its dimensions"))
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText(
            "e.g. steel L-bracket, 150 x 80 x 6 mm, four M8 holes, 8 mm inner fillet"
        )
        layout.addWidget(self.prompt)

        row = QHBoxLayout()
        self.part_hint = QComboBox()
        self.part_hint.addItem("Auto")
        for pt in schemas.PART_SCHEMAS:
            self.part_hint.addItem(pt)
        row.addWidget(QLabel("Part type:"))
        row.addWidget(self.part_hint)
        layout.addLayout(row)

        self.freeform = QCheckBox("Advanced: freeform geometry")
        layout.addWidget(self.freeform)

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.clicked.connect(self._emit)
        layout.addWidget(self.generate_btn)

    def _emit(self) -> None:
        hint = self.part_hint.currentText()
        self.generateRequested.emit(
            self.prompt.toPlainText().strip(),
            "" if hint == "Auto" else hint,
            self.freeform.isChecked(),
        )


class ParameterPanel(QGroupBox):
    """Auto-generated editable fields for the current spec's numeric parameters."""

    paramsChanged = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Parameters", parent)
        self._form = QFormLayout(self)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._suppress = False

    def set_specification(self, parameters: dict[str, Any]) -> None:
        # Rebuild the form from scratch.
        while self._form.rowCount():
            self._form.removeRow(0)
        self._spins.clear()
        for key, value in parameters.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                spin = QDoubleSpinBox()
                spin.setRange(0.0, MAX_PART_ENVELOPE_MM)
                spin.setDecimals(2)
                spin.setValue(float(value))
                spin.valueChanged.connect(self._on_change)
                self._spins[key] = spin
                self._form.addRow(key, spin)
            else:
                self._form.addRow(key, QLabel(str(value)))

    def _on_change(self, _value: float) -> None:
        if self._suppress:
            return
        self.paramsChanged.emit({k: s.value() for k, s in self._spins.items()})


class CorrectionPanel(QWidget):
    correctRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ask AI to change..."))
        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("e.g. make it 8 mm thick")
        send = QPushButton("Apply")
        send.clicked.connect(lambda: self.correctRequested.emit(self.edit.text().strip()))
        row.addWidget(self.edit)
        row.addWidget(send)
        layout.addLayout(row)
        layout.addWidget(QLabel("History"))
        self.history = QListWidget()
        layout.addWidget(self.history)


class ExportBar(QWidget):
    exportRequested = Signal(str)
    materialChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Material:"))
        self.material = QComboBox()
        for m in MATERIAL_DENSITIES:
            self.material.addItem(m)
        self.material.currentTextChanged.connect(self.materialChanged.emit)
        layout.addWidget(self.material)
        for fmt in EXPORT_FORMATS:
            btn = QPushButton(fmt)
            btn.clicked.connect(lambda _=False, f=fmt: self.exportRequested.emit(f))
            btn.setEnabled(False)
            layout.addWidget(btn)
        self._buttons = layout

    def set_enabled(self, enabled: bool) -> None:
        for i in range(self._buttons.count()):
            w = self._buttons.itemAt(i).widget()
            if isinstance(w, QPushButton):
                w.setEnabled(enabled)
