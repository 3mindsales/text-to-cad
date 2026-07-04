"""Application entry point.

Boots, loads config, runs the first-run hardware probe, constructs the configured
(gated) LLM backend, and opens the main window (SPEC 1, 10). License activation is
wired in Phase 7.

Run with:  ``python -m texttocad.app``
"""

from __future__ import annotations

import sys

from texttocad import config
from texttocad.logging_setup import setup_logging


def _build_backend(settings: config.Settings, hw: config.HardwareInfo):
    """Construct the gated backend; fall back to a local Ollama backend on refusal."""
    from texttocad.llm import router
    from texttocad.llm.base import ExternalProviderRefused

    try:
        return router.build_backend(settings, hw)
    except ExternalProviderRefused:
        from texttocad.llm.ollama_backend import OllamaBackend

        tier = router.resolve_tier(settings, hw)
        return OllamaBackend(host=settings.ollama_host, model_tag=router.tier_tag(tier))


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

    from PySide6.QtWidgets import QApplication

    from texttocad.ui.main_window import MainWindow

    qt_app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    backend = _build_backend(settings, hw)
    window = MainWindow(backend, settings, hw)
    window.show()
    return int(qt_app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
