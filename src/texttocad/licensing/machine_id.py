"""Per-machine identity (SPEC 9.1).

``machine_hash()`` returns a stable machine id (Windows UUID / motherboard serial, no
admin). The ``machineid`` import is lazy so the package imports without the optional dep.
"""

from __future__ import annotations


def machine_hash() -> str:
    """Stable per-machine id; raises RuntimeError if the machineid backend is missing."""
    try:
        import machineid
    except ImportError as exc:  # pragma: no cover - dep present in the bundle
        raise RuntimeError("py-machineid is not installed") from exc
    return str(machineid.id())
