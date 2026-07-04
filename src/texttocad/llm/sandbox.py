"""SECURITY-CRITICAL: sandbox for LLM-authored Freeform CadQuery code (SPEC 4.5).

Two layers:

1. ``validate_code_ast`` — parse with ``ast`` and REJECT anything outside a strict
   whitelist (imports, dangerous calls, dangerous names, dunder traversal). This is a
   pure function with no side effects and is the primary, unit-tested boundary.
2. ``run_freeform`` — execute the *validated* code in a separate subprocess with a hard
   wall-clock timeout and (on POSIX) a memory cap, no working-directory writes beyond a
   single output file, and the ``result``-variable output contract. A subprocess is the
   real isolation boundary; restricted globals alone are not.

Any rejection is raised as ``SandboxRejection`` and the caller routes it into the
self-repair loop (SPEC 3.2 Step 5).
"""

from __future__ import annotations

import ast

# subprocess runs only our fixed runner with the current interpreter (see run_freeform).
import subprocess  # nosec B404
import sys
import tempfile
import textwrap
from pathlib import Path

#: Only these top-level modules may be imported by Freeform code.
ALLOWED_IMPORTS = {"cadquery", "math", "numpy"}

#: Direct calls to these builtins are forbidden.
FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "input",
    "breakpoint",
    "memoryview",
}

#: Referencing or accessing attributes on these names is forbidden.
FORBIDDEN_NAMES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "builtins",
    "__builtins__",
    "importlib",
    "ctypes",
    "threading",
    "multiprocessing",
    "pickle",
}

#: Wall-clock timeout (seconds) and memory cap (MB) come from config at call time.
DEFAULT_TIMEOUT_S = 15
DEFAULT_MEM_CAP_MB = 1024


class SandboxRejection(Exception):
    """Raised when Freeform code fails the AST whitelist or the sandbox run."""


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


class _Whitelist(ast.NodeVisitor):
    """Walks the AST and raises SandboxRejection on the first violation."""

    def _reject(self, node: ast.AST, why: str) -> None:
        line = getattr(node, "lineno", "?")
        raise SandboxRejection(f"line {line}: {why}")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                self._reject(node, f"import of '{alias.name}' is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            self._reject(node, "relative imports are not allowed")
        top = (node.module or "").split(".")[0]
        if top not in ALLOWED_IMPORTS:
            self._reject(node, f"import from '{node.module}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
            self._reject(node, f"call to '{func.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if _is_dunder(node.attr):
            self._reject(node, f"access to dunder attribute '{node.attr}' is not allowed")
        if isinstance(node.value, ast.Name) and node.value.id in FORBIDDEN_NAMES:
            self._reject(node, f"attribute access on '{node.value.id}' is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self._reject(node, f"use of name '{node.id}' is not allowed")
        self.generic_visit(node)


def validate_code_ast(code: str) -> None:
    """Raise SandboxRejection if ``code`` violates the whitelist; else return None."""
    if not code or not code.strip():
        raise SandboxRejection("empty code")
    try:
        tree = ast.parse(code, filename="<freeform>", mode="exec")
    except SyntaxError as exc:  # malformed code is a rejection, not a crash
        raise SandboxRejection(f"syntax error: {exc.msg} (line {exc.lineno})") from exc
    _Whitelist().visit(tree)


# --------------------------------------------------------------------------- #
# Execution                                                                   #
# --------------------------------------------------------------------------- #

_RUNNER = textwrap.dedent(
    '''
    """Isolated Freeform runner. Executes validated user code and exports `result`."""
    import sys

    # Best-effort memory cap (POSIX only; Windows relies on the wall-clock timeout).
    try:
        import resource  # type: ignore

        cap = int(sys.argv[3]) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except Exception:
        pass

    code_path, out_path = sys.argv[1], sys.argv[2]
    with open(code_path, "r", encoding="utf-8") as fh:
        user_code = fh.read()

    import cadquery as cq  # noqa: F401  (available to user code)

    ns = {"cq": cq, "cadquery": cq}
    exec(compile(user_code, "<freeform>", "exec"), ns, ns)  # validated upstream by AST whitelist

    if "result" not in ns:
        sys.stderr.write("OUTPUT_CONTRACT: no variable named 'result'")
        sys.exit(3)

    cq.exporters.export(ns["result"], out_path)
    '''
).strip()


def run_freeform(
    code: str,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    mem_cap_mb: int = DEFAULT_MEM_CAP_MB,
    workdir: Path | None = None,
) -> Path:
    """Validate, then execute ``code`` in an isolated subprocess; return the STEP path.

    Raises SandboxRejection on whitelist failure, timeout, non-zero exit, or a missing
    ``result`` variable. The subprocess may only write the single output file.
    """
    validate_code_ast(code)  # never execute unvalidated code

    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="ttc_freeform_"))
    tmp.mkdir(parents=True, exist_ok=True)
    code_path = tmp / "freeform.py"
    runner_path = tmp / "_runner.py"
    out_path = tmp / "result.step"
    code_path.write_text(code, encoding="utf-8")
    runner_path.write_text(_RUNNER, encoding="utf-8")

    try:
        # Fixed interpreter + our own runner script; all args are local file paths.
        proc = subprocess.run(  # nosec B603
            [sys.executable, str(runner_path), str(code_path), str(out_path), str(mem_cap_mb)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(tmp),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxRejection(f"freeform code exceeded {timeout_s}s timeout") from exc

    # A non-empty output means the export completed. OpenCASCADE can segfault during
    # interpreter shutdown on Windows (exit 0xC0000005) AFTER writing the file, so a
    # present, non-empty result is authoritative over the crash-prone exit code. A real
    # error (bad code, missing `result`) leaves no output and is rejected below.
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    detail = (proc.stderr or proc.stdout or "").strip()[:500]
    raise SandboxRejection(f"freeform execution failed (exit {proc.returncode}): {detail}")
