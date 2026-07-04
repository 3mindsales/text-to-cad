"""Embedded 3D viewer (SPEC 7).

Uses a pyvistaqt ``QtInteractor`` when VTK is available; if VTK/GPU init fails it
degrades to a software fallback label instead of crashing the app (SPEC 12 S9). The
solid is tessellated at the fixed 0.1 mm tolerance (SPEC 5.2/7.1).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from texttocad.config import LINEAR_DEFLECTION_MM

logger = logging.getLogger("texttocad.viewer")

_NEUTRAL_GREY = "#CCCCCC"


class Viewer(QWidget):
    """3D viewer widget with a graceful non-GPU fallback."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._plotter: Any = None
        self._fallback: QLabel | None = None
        self._dims_label = QLabel("")
        self._dims_label.setStyleSheet("color: #555555; padding: 4px;")
        self._dims_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._init_plotter()
        self._layout.addWidget(self._dims_label)

    def _init_plotter(self) -> None:
        try:
            from pyvistaqt import QtInteractor

            self._plotter = QtInteractor(self)
            self._layout.addWidget(self._plotter.interactor)
            self._plotter.set_background("white")
        except Exception as exc:  # pragma: no cover - depends on GPU/VTK availability
            logger.warning("VTK viewer unavailable, using software fallback: %s", exc)
            self._show_fallback(str(exc))

    def _show_fallback(self, reason: str) -> None:
        self._fallback = QLabel(
            "3D viewer unavailable on this machine (software fallback).\n"
            "Geometry, validation, and export still work.\n"
            f"\n{reason}"
        )
        self._fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback.setStyleSheet("color: #555555; background: #F5F5F5;")
        self._layout.addWidget(self._fallback)

    @property
    def has_gpu_viewer(self) -> bool:
        return self._plotter is not None

    def show_solid(self, wp: Any, warnings: list[str] | None = None) -> None:
        """Tessellate and display a CadQuery solid (or update the fallback dims)."""
        bbox = self._bbox(wp)
        self._dims_label.setText(f"Overall (L x W x H): {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm")
        if not self._plotter:
            if self._fallback is not None:
                self._fallback.setText(
                    f"3D viewer unavailable (software fallback).\n"
                    f"Model bounding box: {bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f} mm"
                )
            return
        try:
            import numpy as np
            import pyvista as pv

            verts, tris = wp.val().tessellate(LINEAR_DEFLECTION_MM)
            points = np.array([[v.x, v.y, v.z] for v in verts], dtype=float)
            faces = np.hstack([[3, *t] for t in tris]).astype(np.int64) if tris else np.array([])
            mesh = pv.PolyData(points, faces)
            self._plotter.clear()
            colour = "#F5A623" if warnings else _NEUTRAL_GREY
            self._plotter.add_mesh(mesh, color=colour, show_edges=True, edge_color="#888888")
            self._plotter.reset_camera()
        except Exception as exc:  # pragma: no cover - rendering path
            logger.warning("failed to render solid: %s", exc)

    def clear(self) -> None:
        if self._plotter:
            try:
                self._plotter.clear()
            except Exception as exc:  # pragma: no cover
                logger.debug("viewer clear failed: %s", exc)
        self._dims_label.setText("")

    @staticmethod
    def _bbox(wp: Any) -> tuple[float, float, float]:
        try:
            bb = wp.val().BoundingBox()
            return (bb.xlen, bb.ylen, bb.zlen)
        except Exception:  # pragma: no cover - defensive
            return (0.0, 0.0, 0.0)
