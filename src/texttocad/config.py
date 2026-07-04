"""Typed application configuration and first-run hardware probe.

Settings are loaded from (in increasing precedence):
    1. built-in defaults (this module),
    2. a JSON config file (``%APPDATA%/TextToCAD/config.json`` by default),
    3. environment variables (``TEXTTOCAD_*`` and the spec-defined ``AIRGAP_STRICT``).

The config is a plain dataclass (no pydantic-settings dependency) so it stays
importable with zero heavy deps — the shell must boot before CadQuery/VTK exist.

Spec references: SPEC 4.2 (model tiers / hardware probe), 4.6 (prompt version),
5.2/5.5 (geometry constants), 9.5 (AIRGAP_STRICT), 8.4 (material densities).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Constants (fixed by the spec; not user-tunable via the normal settings file) #
# --------------------------------------------------------------------------- #

APP_NAME = "TextToCAD"
APP_VERSION = "0.1.0"
PROMPT_TEMPLATE_VERSION = "v1"  # bumped whenever the shipped system prompt changes

#: Self-repair retries before the pipeline gives up (SPEC 3.2 Step 5).
LLM_MAX_REPAIRS = 3
#: Wall-clock timeout for sandboxed freeform code, seconds (SPEC 4.5).
LLM_CODE_TIMEOUT = 15
#: Memory cap for the sandbox subprocess, MB (SPEC 4.5).
LLM_CODE_MEM_CAP_MB = 1024

#: Fixed tessellation tolerances for determinism (SPEC 5.2).
LINEAR_DEFLECTION_MM = 0.1
ANGULAR_DEFLECTION_RAD = 0.5

#: Geometry validation guards (SPEC 5.5).
MAX_PART_ENVELOPE_MM = 5000.0  # 5 m per axis
MIN_WALL_MM = 1.5
MIN_EDGE_DISTANCE_FACTOR = 1.5  # x hole diameter

#: Local Ollama endpoint (SPEC 4.1).
OLLAMA_HOST_DEFAULT = "127.0.0.1:11434"

#: Material densities in kg/m^3 for mass/cut-list (SPEC 8.4).
MATERIAL_DENSITIES: dict[str, float] = {
    "mild_steel": 7850.0,
    "aluminium": 2700.0,
    "stainless": 8000.0,
}

#: Model tiers keyed by id, with a rough minimum-RAM heuristic (GB) for selection.
MODEL_TIERS: dict[str, dict[str, object]] = {
    "3b": {"tag": "qwen2.5-coder:3b-instruct", "min_ram_gb": 4, "force_template": True},
    "7b": {"tag": "qwen2.5-coder:7b-instruct", "min_ram_gb": 8, "force_template": False},
    "14b": {"tag": "qwen2.5-coder:14b-instruct", "min_ram_gb": 16, "force_template": False},
    "32b": {"tag": "qwen2.5-coder:32b-instruct", "min_ram_gb": 32, "force_template": False},
}


def _default_config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """User-tunable settings, persisted as JSON and overridable by env vars."""

    active_backend: str = "ollama"
    active_model_tier: str = "7b"
    ollama_host: str = OLLAMA_HOST_DEFAULT
    airgap_strict: bool = False
    allow_external_llm: bool = False
    freeform_enabled: bool = False
    output_dir: str = field(default_factory=lambda: str(Path.home() / "TextToCAD_Output"))
    units_display: str = "mm"  # "mm" | "inch"
    material: str = "mild_steel"

    # ------------------------------------------------------------------ #
    # Loading / persistence                                              #
    # ------------------------------------------------------------------ #
    @classmethod
    def config_path(cls) -> Path:
        override = os.environ.get("TEXTTOCAD_CONFIG")
        if override:
            return Path(override)
        return _default_config_dir() / "config.json"

    @classmethod
    def load(cls) -> Settings:
        """Load defaults, overlay the JSON file, then apply env overrides."""
        data: dict[str, Any] = {}
        path = cls.config_path()
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (json.JSONDecodeError, OSError):
                data = {}
        known = set(cls.__dataclass_fields__)
        filtered: dict[str, Any] = {k: v for k, v in data.items() if k in known}
        settings = cls(**filtered)
        settings._apply_env_overrides()
        return settings

    def _apply_env_overrides(self) -> None:
        # AIRGAP_STRICT is spec-named (SPEC 9.5) — honour it without the prefix too.
        self.airgap_strict = _env_bool("AIRGAP_STRICT", self.airgap_strict) or _env_bool(
            "TEXTTOCAD_AIRGAP_STRICT", self.airgap_strict
        )
        self.allow_external_llm = _env_bool("TEXTTOCAD_ALLOW_EXTERNAL_LLM", self.allow_external_llm)
        if os.environ.get("TEXTTOCAD_BACKEND"):
            self.active_backend = os.environ["TEXTTOCAD_BACKEND"]
        if os.environ.get("TEXTTOCAD_MODEL_TIER"):
            self.active_model_tier = os.environ["TEXTTOCAD_MODEL_TIER"]
        if os.environ.get("TEXTTOCAD_OUTPUT_DIR"):
            self.output_dir = os.environ["TEXTTOCAD_OUTPUT_DIR"]
        if os.environ.get("OLLAMA_HOST"):
            self.ollama_host = os.environ["OLLAMA_HOST"]
        # In a strict air-gapped build cloud/external must be impossible (SPEC 9.5).
        if self.airgap_strict:
            self.allow_external_llm = False

    def save(self) -> Path:
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path


@dataclass
class HardwareInfo:
    """Result of the first-run hardware probe (SPEC 4.2)."""

    total_ram_gb: float
    vram_gb: float | None
    has_nvidia_gpu: bool
    recommended_tier: str


def _probe_ram_gb() -> float:
    try:
        import psutil

        return float(round(psutil.virtual_memory().total / (1024**3), 1))
    except Exception:  # pragma: no cover - psutil should be present
        # Fallback for environments without psutil (e.g. minimal POSIX).
        sysconf = getattr(os, "sysconf", None)
        if sysconf is None:
            return 0.0
        try:
            total = sysconf("SC_PAGE_SIZE") * sysconf("SC_PHYS_PAGES")
            return float(round(total / (1024**3), 1))
        except (ValueError, OSError):
            return 0.0


def _probe_vram_gb() -> float | None:
    """Best-effort NVIDIA VRAM probe via nvidia-smi; None if no GPU/tool."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    first = out.stdout.strip().splitlines()
    if not first:
        return None
    try:
        mib = float(first[0].strip())
    except ValueError:
        return None
    return round(mib / 1024, 1)


def recommend_tier(total_ram_gb: float, vram_gb: float | None) -> str:
    """Pick the best model tier that fits the detected hardware (SPEC 4.2).

    A discrete GPU with enough VRAM lets us go one tier higher; otherwise we
    fall back to system RAM (CPU inference).
    """
    budget_gb = max(total_ram_gb, (vram_gb or 0.0) * 1.5)
    if budget_gb >= 32:
        return "32b"
    if budget_gb >= 16:
        return "14b"
    if budget_gb >= 8:
        return "7b"
    return "3b"


def probe_hardware() -> HardwareInfo:
    """Run the first-run hardware probe and recommend a local model tier."""
    ram = _probe_ram_gb()
    vram = _probe_vram_gb()
    tier = recommend_tier(ram, vram)
    return HardwareInfo(
        total_ram_gb=ram,
        vram_gb=vram,
        has_nvidia_gpu=vram is not None,
        recommended_tier=tier,
    )
