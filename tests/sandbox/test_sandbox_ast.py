"""Sandbox AST-whitelist suite — the permanent security regression guard (I6, SPEC 4.5).

Must reject the documented malicious-snippet set and accept benign CadQuery code.
"""

from __future__ import annotations

import pytest

from texttocad.llm.sandbox import SandboxRejection, validate_code_ast

MALICIOUS = [
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import shutil",
    "from os import system",
    "from pathlib import Path",
    "os.system('rm -rf /')",
    "open('/etc/passwd').read()",
    "__import__('os').system('x')",
    "eval('2+2')",
    "exec('x=1')",
    "compile('1', '<s>', 'eval')",
    "getattr(cq, 'foo')",
    "setattr(cq, 'foo', 1)",
    "().__class__.__bases__[0].__subclasses__()",
    "cq.__globals__",
    "result = (1).__class__",
    "import ctypes",
    "import importlib",
    "x = globals()",
]

BENIGN = [
    "result = cq.Workplane('XY').box(10, 10, 2)",
    "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 10, 2)",
    "import math\nresult = cq.Workplane('XY').circle(math.pi).extrude(2)",
    "import numpy as np\nr = float(np.sqrt(4))\nresult = cq.Workplane('XY').box(r, r, 1)",
    "from cadquery import Workplane\nresult = Workplane('XY').box(5, 5, 5)",
]


@pytest.mark.parametrize("code", MALICIOUS)
def test_rejects_malicious(code):
    with pytest.raises(SandboxRejection):
        validate_code_ast(code)


@pytest.mark.parametrize("code", BENIGN)
def test_accepts_benign(code):
    # Should not raise.
    validate_code_ast(code)


def test_rejects_empty_and_syntax_error():
    with pytest.raises(SandboxRejection):
        validate_code_ast("")
    with pytest.raises(SandboxRejection):
        validate_code_ast("def broken(:\n  pass")
