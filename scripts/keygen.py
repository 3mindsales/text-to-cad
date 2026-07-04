"""Vendor key generation (run ONCE, offline). Writes:

  src/texttocad/licensing/public_key.pem   -> bundled in the app (SPEC 9.2)
  _vendor/private_key.pem                   -> KEPT BY VENDOR ONLY, never bundled/committed

Production uses 4096-bit (spec). Pass a size arg to override (tests use 2048 for speed).
    python scripts/keygen.py [bits]
"""

from __future__ import annotations

import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB_PATH = os.path.join(ROOT, "src", "texttocad", "licensing", "public_key.pem")
VENDOR_DIR = os.path.join(ROOT, "_vendor")


def main(bits: int = 4096) -> None:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with open(PUB_PATH, "wb") as f:
        f.write(pub_pem)
    os.makedirs(VENDOR_DIR, exist_ok=True)
    with open(os.path.join(VENDOR_DIR, "private_key.pem"), "wb") as f:
        f.write(priv_pem)
    print(f"wrote {PUB_PATH}")
    print(f"wrote {VENDOR_DIR}/private_key.pem ({bits}-bit) - keep private, do NOT bundle/commit")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4096)
