"""Per-session conversion report (SPEC 8.5).

Records provenance and reproducibility data: app + prompt version, the active backend
(with the is_local flag), the user prompt, the final validated specification (or a code
hash for freeform), repair count, validation result, warnings, exported files, and stage
timings. The prompt VERSION is logged, not the full prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from texttocad import config
from texttocad.pipeline.generate import Specification


@dataclass
class ReportData:
    user_prompt: str
    spec: Specification | None
    backend_name: str
    model: str
    is_local: bool
    repair_attempts: int
    validation_summary: str
    warnings: list[str] = field(default_factory=list)
    exported_files: list[Path] = field(default_factory=list)
    stage_timings_s: dict[str, float] = field(default_factory=dict)
    timestamp: str = ""  # caller stamps this (no time in the library layer)


def render_report(data: ReportData) -> str:
    lines: list[str] = []
    lines.append("TextToCAD conversion report")
    lines.append("=" * 40)
    lines.append(f"timestamp:        {data.timestamp}")
    lines.append(f"app version:      {config.APP_VERSION}")
    lines.append(f"prompt version:   {config.PROMPT_TEMPLATE_VERSION}")
    lines.append(f"backend:          {data.backend_name}")
    lines.append(f"model:            {data.model}")
    lines.append(f"is_local:         {data.is_local}")
    lines.append(f"user prompt:      {data.user_prompt}")
    if data.spec is not None:
        lines.append(f"mode:             {data.spec.mode}")
        lines.append(f"part_type:        {data.spec.part_type}")
        if data.spec.mode == "freeform":
            lines.append(f"code hash:        {data.spec.spec_hash()}")
        else:
            lines.append(f"parameters:       {data.spec.parameters}")
        lines.append(f"spec hash:        {data.spec.spec_hash()}")
    lines.append(f"repair attempts:  {data.repair_attempts}")
    lines.append(f"validation:       {data.validation_summary}")
    lines.append("warnings:")
    for w in data.warnings or ["(none)"]:
        lines.append(f"  - {w}")
    lines.append("exported files:")
    for f in data.exported_files or []:
        try:
            size = Path(f).stat().st_size
        except OSError:
            size = 0
        lines.append(f"  - {Path(f).name} ({size} bytes)")
    if not data.exported_files:
        lines.append("  - (none)")
    lines.append("stage timings (s):")
    for stage, secs in (data.stage_timings_s or {}).items():
        lines.append(f"  - {stage}: {secs:.3f}")
    lines.append("")
    return "\n".join(lines)


def write_report(path: str | Path, data: ReportData) -> Path:
    path = Path(path)
    path.write_text(render_report(data), encoding="utf-8")
    return path
