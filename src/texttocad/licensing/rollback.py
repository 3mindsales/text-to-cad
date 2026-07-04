"""Clock-rollback guard (SPEC 9.3). Adapted from the IFC suite (ADR-0005).

Stores a monotonic "last seen" UTC timestamp; if the system clock is ever earlier than
the stored value, the app locks. The store is abstracted so the logic is testable
headless; production uses the HKCU registry (no admin). Anti-casual-tamper only. A
missing stored value is treated as first run. The optional NTP cross-check fails cleanly
(returns None) when air-gapped so the registry check still governs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_TAMPERED = "System clock tampered - license revoked"


class InMemoryStore:
    """Test/abstract store."""

    def __init__(self, value: str | None = None) -> None:
        self._v = value

    def get(self) -> str | None:
        return self._v

    def set(self, value: str) -> None:
        self._v = value


class RegistryStore:
    """Production store: HKEY_CURRENT_USER (no admin). Windows only."""

    def __init__(self, subkey: str = r"Software\TextToCAD", name: str = "last_seen_utc") -> None:
        self.subkey, self.name = subkey, name

    def get(self) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
                return str(winreg.QueryValueEx(k, self.name)[0])
        except OSError:
            return None

    def set(self, value: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.subkey) as k:
            winreg.SetValueEx(k, self.name, 0, winreg.REG_SZ, value)


def ntp_utc(server: str = "pool.ntp.org", timeout: float = 2.0) -> datetime | None:
    """Best-effort UTC from NTP (SPEC 9.3). Returns None when unreachable/offline."""
    try:
        import ntplib

        resp = ntplib.NTPClient().request(server, version=3, timeout=timeout)
        return datetime.fromtimestamp(resp.tx_time, tz=UTC)
    except Exception:
        return None


def check_clock(
    store,
    now: datetime | None = None,
    ntp: datetime | None = None,
    ntp_tolerance_days: int = 1,
) -> tuple[bool, str]:
    """Return (ok, reason). Locks on rollback vs the stored stamp (or, with an NTP time,
    if the clock sits well behind real time). Advances the stored stamp on success."""
    now = now or datetime.now(UTC)
    if ntp is not None and now < ntp - timedelta(days=ntp_tolerance_days):
        return False, _TAMPERED
    stored_raw = store.get()
    if stored_raw:
        stored = datetime.fromisoformat(stored_raw)
        if now < stored:
            return False, _TAMPERED
        if now > stored:
            store.set(now.isoformat())
    else:
        store.set(now.isoformat())  # first run
    return True, ""
