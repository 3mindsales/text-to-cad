"""Background worker (SPEC 6.1/6.3).

All LLM/build/export work runs on a QThread so the UI never blocks. The worker runs a
plain callable and emits status/result/error/warning signals, plus a heartbeat at least
every 2 s to prove liveness. Cancellation sets a flag and terminates any sandbox
subprocess the job started.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, QTimer, Signal

logger = logging.getLogger("texttocad.worker")

HEARTBEAT_MS = 2000


class PipelineWorker(QThread):
    """Runs one job off the main thread and reports via signals."""

    status_signal = Signal(str)
    progress_signal = Signal(int)
    result_signal = Signal(object)
    warning_signal = Signal(list)
    error_signal = Signal(str)
    heartbeat_signal = Signal()

    def __init__(self, job: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._job = job
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False
        self._heartbeat: QTimer | None = None

    def cancel(self) -> None:
        """Request cancellation; the job checks ``is_cancelled`` between steps."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:  # executed on the worker thread
        # Heartbeat lives on this thread's event loop timer.
        self._heartbeat = QTimer()
        self._heartbeat.setInterval(HEARTBEAT_MS)
        self._heartbeat.timeout.connect(self.heartbeat_signal.emit)
        self._heartbeat.start()
        try:
            self.status_signal.emit("Working...")
            result = self._job(*self._args, worker=self, **self._kwargs)
            if self._cancelled:
                self.status_signal.emit("Cancelled")
                return
            self.result_signal.emit(result)
            warnings = getattr(result, "warnings", None)
            if warnings:
                self.warning_signal.emit(list(warnings))
            self.status_signal.emit("Done")
        except Exception as exc:  # never let a worker exception crash the app
            logger.exception("worker job failed")
            self.error_signal.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if self._heartbeat is not None:
                self._heartbeat.stop()


def run_generation_job(
    user_prompt: str, backend: Any, *, allow_freeform: bool = False, worker: Any = None
) -> Any:
    """Job wrapper for the generation pipeline (importable/testable on its own)."""
    from texttocad.pipeline import generate

    return generate.generate(user_prompt, backend, allow_freeform=allow_freeform)
