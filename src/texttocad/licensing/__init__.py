"""Licensing (SPEC 9) — machine-locked RSA license + clock-rollback guard.

Qt-free and unit-testable with a throwaway keypair. The app's public key is bundled
(``public_key.pem``); the private key stays with the vendor and is used only by the
offline signing tool (``scripts/sign_license.py``). Obfuscation via Cython (ADR-0005).
"""

from texttocad.licensing.machine_id import machine_hash
from texttocad.licensing.rollback import (
    InMemoryStore,
    RegistryStore,
    check_clock,
    ntp_utc,
)
from texttocad.licensing.rsa_verify import (
    LicenseResult,
    canonical_payload,
    load_public_key_pem,
    sign_license,
    verify_file,
    verify_license,
)

__all__ = [
    "LicenseResult",
    "machine_hash",
    "canonical_payload",
    "sign_license",
    "verify_license",
    "verify_file",
    "load_public_key_pem",
    "InMemoryStore",
    "RegistryStore",
    "check_clock",
    "ntp_utc",
]
