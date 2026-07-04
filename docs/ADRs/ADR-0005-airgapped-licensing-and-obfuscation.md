# ADR-0005 — Air-gapped licensing (RSA + machine hash + clock-rollback); Cython obfuscation

- Status: Accepted
- Date: 2026-07-04

## Context

The product ships to on-prem/air-gapped clients and must be licensed without any license server.
The IFC suite already implements a proven, offline licensing model we reuse verbatim in intent.
SPEC §9.4 names PyArmor for obfuscating the licensing/hashing modules; the reused implementation
instead uses a Cython → native `.pyd` compile, which is free and does not trip antivirus.

## Decision

- **Licensing:** a 4096-bit RSA public key is bundled; `license.key` is JSON
  `{machine_hash, expiry, signature}` verified with `cryptography` (PKCS1v15 + SHA-256) over a
  canonical serialization; machine binding via `machineid.id()`; expiry checked. The app is locked
  until activation succeeds.
- **Clock-rollback protection:** last-validation UTC is stored in the Windows Registry
  (`HKCU`, no admin); startup locks if system time < stored ("System clock tampered — license
  revoked"). Optional NTP cross-check fails cleanly when air-gapped.
- **Obfuscation:** deviate from SPEC §9.4's PyArmor and use the house-proven **Cython → `.pyd`**
  approach (`scripts/obfuscate_licensing.py`), plus PyInstaller `--strip`, `--noupx`, and no
  logic-revealing prints/tracebacks on the user surface.

## Consequences

- Fully offline activation; no telemetry, no license server.
- Documented, intentional deviation from SPEC §9.4 (PyArmor → Cython) — recorded here so docs and
  code agree. Same security intent (§9.4), lower cost and fewer AV false positives.
- The signer's canonical payload must byte-match the verifier's, or verification silently fails —
  this is covered by the licensing test suite (valid / wrong-hash / expired / tampered / rollback).
