"""RSA license validation (SPEC 9.2). Adapted from the IFC suite (ADR-0005).

License = JSON ``{machine_hash, expiry (YYYY-MM-DD), signature (base64)}``. The signature
is over a CANONICAL serialization of ``{machine_hash, expiry}`` (sorted keys, no
whitespace) — signer and verifier must produce identical bytes or verification fails.
PKCS1v15 + SHA-256, ``cryptography`` hazmat only (pycryptodome forbidden by SPEC 9).

All validation failures return the SAME generic message so the failure reason is not a
tampering oracle.
"""

from __future__ import annotations

import base64
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from texttocad.licensing.machine_id import machine_hash

_GENERIC = "Invalid license - contact vendor"


@dataclass
class LicenseResult:
    ok: bool
    reason: str = ""


def public_key_path() -> Path:
    """Locate the bundled public key PEM (``_MEIPASS``-aware for a frozen build)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "texttocad" / "licensing" / "public_key.pem"
        if p.exists():
            return p
    return Path(__file__).parent / "public_key.pem"


def load_public_key_pem() -> bytes:
    return public_key_path().read_bytes()


def canonical_payload(machine_hash_: str, expiry: str) -> bytes:
    return json.dumps(
        {"machine_hash": machine_hash_, "expiry": expiry}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_license(private_key, machine_hash_: str, expiry: str) -> dict:
    """VENDOR/test side: produce a license dict signed with the RSA private key."""
    sig = private_key.sign(canonical_payload(machine_hash_, expiry), padding.PKCS1v15(), hashes.SHA256())
    return {
        "machine_hash": machine_hash_,
        "expiry": expiry,
        "signature": base64.b64encode(sig).decode("ascii"),
    }


def verify_license(
    license: dict,
    public_key_pem: bytes,
    *,
    current_machine: str | None = None,
    today: date | None = None,
) -> LicenseResult:
    """APP side: verify signature, machine binding, and expiry."""
    current_machine = current_machine or machine_hash()
    today = today or date.today()
    try:
        pub = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(pub, rsa.RSAPublicKey):
            raise ValueError("bundled key is not an RSA public key")
        sig = base64.b64decode(license["signature"])
        payload = canonical_payload(license["machine_hash"], license["expiry"])
        pub.verify(sig, payload, padding.PKCS1v15(), hashes.SHA256())
    except (KeyError, ValueError, InvalidSignature, TypeError):
        return LicenseResult(False, _GENERIC)
    if license["machine_hash"] != current_machine:
        return LicenseResult(False, _GENERIC)  # wrong machine
    try:
        exp = date.fromisoformat(license["expiry"])
    except ValueError:
        return LicenseResult(False, _GENERIC)
    if today > exp:
        return LicenseResult(False, _GENERIC)  # expired
    return LicenseResult(True, "")


def verify_file(path: str | None) -> LicenseResult:
    """Verify a license file on disk for THIS machine (any problem -> generic failure)."""
    if not path:
        return LicenseResult(False, _GENERIC)
    try:
        with open(path, encoding="utf-8") as f:
            lic = json.load(f)
    except (OSError, ValueError):
        return LicenseResult(False, _GENERIC)
    if not isinstance(lic, dict):
        return LicenseResult(False, _GENERIC)
    try:
        pub_pem = load_public_key_pem()
    except OSError:
        return LicenseResult(False, _GENERIC)
    return verify_license(lic, pub_pem, current_machine=machine_hash())
