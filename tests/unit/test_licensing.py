"""Licensing tests (SPEC 9): RSA verify + machine binding + expiry + clock rollback.

Uses a throwaway 2048-bit keypair (fast); never touches the bundled production key.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from texttocad import licensing
from texttocad.licensing import rsa_verify

MH = "TEST-MACHINE-HASH-1234"


@pytest.fixture(scope="module")
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return priv, pub_pem


def test_valid_license_unlocks(keypair):
    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2999-01-01")
    res = licensing.verify_license(lic, pub, current_machine=MH, today=date(2026, 7, 4))
    assert res.ok is True


def test_wrong_machine_fails(keypair):
    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2999-01-01")
    res = licensing.verify_license(lic, pub, current_machine="OTHER-MACHINE", today=date(2026, 7, 4))
    assert res.ok is False


def test_expired_fails(keypair):
    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2020-01-01")
    res = licensing.verify_license(lic, pub, current_machine=MH, today=date(2026, 7, 4))
    assert res.ok is False


def test_tampered_signature_fails(keypair):
    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2999-01-01")
    # Tamper with the signed payload after signing.
    lic["expiry"] = "2999-12-31"
    res = licensing.verify_license(lic, pub, current_machine=MH, today=date(2026, 7, 4))
    assert res.ok is False


def test_generic_reason_is_uniform(keypair):
    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2020-01-01")
    r1 = licensing.verify_license(lic, pub, current_machine="X", today=date(2026, 7, 4))
    r2 = licensing.verify_license(lic, pub, current_machine=MH, today=date(2026, 7, 4))
    assert r1.reason == r2.reason  # no oracle: same message for wrong-machine and expired


def test_verify_file_roundtrip(tmp_path, monkeypatch, keypair):
    import json

    priv, pub = keypair
    lic = licensing.sign_license(priv, MH, "2999-01-01")
    path = tmp_path / "license.key"
    path.write_text(json.dumps(lic), encoding="utf-8")
    monkeypatch.setattr(rsa_verify, "load_public_key_pem", lambda: pub)
    monkeypatch.setattr(rsa_verify, "machine_hash", lambda: MH)
    assert licensing.verify_file(str(path)).ok is True
    assert licensing.verify_file(None).ok is False
    assert licensing.verify_file(str(tmp_path / "missing.key")).ok is False


def test_bundled_public_key_present():
    # The production public key ships with the package (private key never committed).
    pem = licensing.load_public_key_pem()
    assert pem.startswith(b"-----BEGIN PUBLIC KEY-----")


# ---- clock rollback ----


def _dt(y, m, d):
    return datetime(y, m, d, tzinfo=UTC)


def test_clock_first_run_ok_and_stamps():
    store = licensing.InMemoryStore()
    ok, _ = licensing.check_clock(store, now=_dt(2026, 7, 4))
    assert ok is True
    assert store.get() is not None


def test_clock_rollback_locks():
    store = licensing.InMemoryStore(_dt(2026, 7, 4).isoformat())
    ok, reason = licensing.check_clock(store, now=_dt(2026, 6, 1))
    assert ok is False
    assert "tampered" in reason.lower()


def test_clock_forward_advances_stamp():
    store = licensing.InMemoryStore(_dt(2026, 7, 4).isoformat())
    ok, _ = licensing.check_clock(store, now=_dt(2026, 7, 5))
    assert ok is True
    assert store.get() == _dt(2026, 7, 5).isoformat()


def test_clock_ntp_behind_locks():
    store = licensing.InMemoryStore()
    ok, reason = licensing.check_clock(store, now=_dt(2026, 7, 4), ntp=_dt(2026, 7, 10))
    assert ok is False
    assert "tampered" in reason.lower()
