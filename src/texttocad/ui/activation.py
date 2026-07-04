"""License activation modal (SPEC 10.2, Window 1).

Shows the machine hash in a copyable box, lets the user browse for a ``license.key``,
and verifies it. Verification is injected (``verify_fn``) so this window has no hard
dependency on the licensing module — Phase 7 wires the real RSA verifier in.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ActivationDialog(QDialog):
    def __init__(
        self,
        machine_hash: str,
        verify_fn: Callable[[str], tuple[bool, str]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._verify_fn = verify_fn
        self._license_path: str | None = None
        self.setWindowTitle("Activate TextToCAD")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Your machine hash (send this to your vendor):"))
        hash_box = QLineEdit(machine_hash)
        hash_box.setReadOnly(True)
        layout.addWidget(hash_box)

        row = QHBoxLayout()
        self.path_label = QLabel("No license.key selected")
        browse = QPushButton("Browse for license.key")
        browse.clicked.connect(self._browse)
        row.addWidget(self.path_label)
        row.addWidget(browse)
        layout.addLayout(row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EA4335;")
        layout.addWidget(self.error_label)

        activate = QPushButton("Activate")
        activate.clicked.connect(self._activate)
        layout.addWidget(activate)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select license.key", "", "License (*.key)")
        if path:
            self._license_path = path
            self.path_label.setText(path)

    def _activate(self) -> None:
        if not self._license_path:
            self.error_label.setText("Please select a license.key file.")
            return
        ok, reason = self._verify_fn(self._license_path)
        if ok:
            self.accept()
        else:
            self.error_label.setText(reason or "License verification failed.")
