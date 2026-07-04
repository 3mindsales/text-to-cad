"""Versioned prompt loader (SPEC 4.6).

The system prompt and few-shot examples are shipped as versioned data files; the loader
returns their text plus the version so results are reproducible across app updates (the
version, not the full text, is logged in the report). Do not build prompt strings inline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROMPT_VERSION = "v1"

_HERE = Path(__file__).parent


@dataclass(frozen=True)
class PromptBundle:
    """A loaded, versioned prompt: system text + few-shot examples."""

    version: str
    system: str
    fewshot: list[dict]

    def build_user_preamble(self) -> str:
        """Render the few-shot examples as a compact user-visible preamble."""
        lines: list[str] = []
        for ex in self.fewshot:
            lines.append(f"USER: {ex['user']}")
            lines.append(f"ASSISTANT: {json.dumps(ex['assistant'], separators=(',', ':'))}")
        return "\n".join(lines)


def load_prompt(version: str = DEFAULT_PROMPT_VERSION) -> PromptBundle:
    """Load the versioned system prompt + few-shot examples.

    Raises FileNotFoundError if the requested version is not shipped.
    """
    system_path = _HERE / f"system_{version}.md"
    fewshot_path = _HERE / f"fewshot_{version}.json"
    if not system_path.exists():
        raise FileNotFoundError(f"prompt version '{version}' not found: {system_path}")
    system = system_path.read_text(encoding="utf-8")
    fewshot: list[dict] = []
    if fewshot_path.exists():
        fewshot = json.loads(fewshot_path.read_text(encoding="utf-8"))
    return PromptBundle(version=version, system=system, fewshot=fewshot)
