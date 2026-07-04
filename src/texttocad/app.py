"""Application entry point.

Phase 1 scope (SPEC 1, 10): boot, load config, run the first-run hardware probe,
and open a bare main window with an LLM status-pill placeholder. No features yet —
the pipeline, viewer, and panels arrive in later phases behind their interfaces.

Run with:  ``python -m texttocad.app``
"""

from __future__ import annotations

import sys

from texttocad import config
from texttocad.logging_setup import setup_logging


def _build_window(settings: config.Settings, hw: config.HardwareInfo):
    """Construct the bare QMainWindow. Imported lazily so non-GUI paths (probe,
    tests) don't require a Qt display."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QVBoxLayout, QWidget

    window = QMainWindow()
    window.setWindowTitle(f"{config.APP_NAME} {config.APP_VERSION}")
    window.resize(1200, 800)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    heading = QLabel(f"{config.APP_NAME}")
    heading.setStyleSheet("font-size: 28px; font-weight: 600; color: #000000;")
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

    subtitle = QLabel("Describe a part and its dimensions — the model comes later.")
    subtitle.setStyleSheet("color: #555555;")
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(heading)
    layout.addWidget(subtitle)
    window.setCentralWidget(central)

    # LLM status pill placeholder (SPEC 10.2): green when local, red when external.
    tier = config.MODEL_TIERS.get(settings.active_model_tier, {})
    tag = tier.get("tag", settings.active_model_tier)
    pill = QLabel(f"  ● {tag}  ")
    # Phase 1: assume local (green). Real is_local() gating lands in Phase 2.
    pill.setStyleSheet("color: #FFFFFF; background: #34A853; border-radius: 8px; padding: 2px 8px;")
    status: QStatusBar = window.statusBar()
    status.addPermanentWidget(pill)
    status.showMessage(
        f"RAM {hw.total_ram_gb} GB | GPU {'yes' if hw.has_nvidia_gpu else 'no'} | "
        f"recommended tier: {hw.recommended_tier}"
    )
    return window


def main(argv: list[str] | None = None) -> int:
    """Boot the application; return a process exit code."""
    settings = config.Settings.load()
    logger = setup_logging(log_dir=config.Settings.config_path().parent)
    logger.info("%s %s starting", config.APP_NAME, config.APP_VERSION)

    hw = config.probe_hardware()
    logger.info(
        "Hardware probe: RAM=%.1f GB, VRAM=%s, NVIDIA GPU=%s -> recommended local tier '%s'",
        hw.total_ram_gb,
        f"{hw.vram_gb} GB" if hw.vram_gb is not None else "n/a",
        hw.has_nvidia_gpu,
        hw.recommended_tier,
    )
    if settings.active_model_tier != hw.recommended_tier:
        logger.info(
            "Configured tier '%s' differs from recommended '%s' (keeping configured)",
            settings.active_model_tier,
            hw.recommended_tier,
        )

    from PySide6.QtWidgets import QApplication

    qt_app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    window = _build_window(settings, hw)
    window.show()
    return int(qt_app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
