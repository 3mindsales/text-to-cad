"""Specification history for Undo/Redo (SPEC 6.2).

Stores validated *specifications* only — never binaries (I2). The stack is capped; a
new push after undos truncates the redo tail (standard linear history). Direct parameter
edits build a new spec via ``with_param_updates`` and are pushed like any other change.
"""

from __future__ import annotations

from typing import Any

from texttocad.pipeline.generate import Specification

HISTORY_CAP = 100


class SpecHistory:
    """A linear, capped Undo/Redo stack of specifications."""

    def __init__(self, cap: int = HISTORY_CAP) -> None:
        self._stack: list[Specification] = []
        self._idx: int = -1
        self._cap = cap

    def push(self, spec: Specification) -> None:
        # Drop any redo tail, then append and enforce the cap.
        del self._stack[self._idx + 1 :]
        self._stack.append(spec)
        if len(self._stack) > self._cap:
            self._stack.pop(0)
        self._idx = len(self._stack) - 1

    @property
    def current(self) -> Specification | None:
        if 0 <= self._idx < len(self._stack):
            return self._stack[self._idx]
        return None

    @property
    def can_undo(self) -> bool:
        return self._idx > 0

    @property
    def can_redo(self) -> bool:
        return self._idx < len(self._stack) - 1

    def undo(self) -> Specification | None:
        if self.can_undo:
            self._idx -= 1
        return self.current

    def redo(self) -> Specification | None:
        if self.can_redo:
            self._idx += 1
        return self.current

    def __len__(self) -> int:
        return len(self._stack)


def with_param_updates(spec: Specification, updates: dict[str, Any]) -> Specification:
    """Return a new spec with ``updates`` merged into its parameters (direct edit path)."""
    from dataclasses import replace

    return replace(spec, parameters={**spec.parameters, **updates})
