"""Sandbox subprocess execution boundary (SPEC 4.5).

These exercise ``run_freeform`` end-to-end without requiring CadQuery: a malicious
snippet is rejected before any subprocess starts, and a snippet that passes the AST
gate but fails at runtime is surfaced as a SandboxRejection (never a crash).
"""

from __future__ import annotations

import pytest

from texttocad.llm.sandbox import SandboxRejection, run_freeform


def test_run_rejects_malicious_before_exec():
    # Fails the whitelist -> raised before any subprocess is spawned.
    with pytest.raises(SandboxRejection):
        run_freeform("import os\nos.system('echo hi')")


def test_run_maps_runtime_error_to_rejection(tmp_path):
    # Passes the AST whitelist but the subprocess exits non-zero (cadquery import or
    # the runtime error) -> SandboxRejection, not an uncaught exception.
    with pytest.raises(SandboxRejection):
        run_freeform("result = 1 / 0", timeout_s=60, workdir=tmp_path)
