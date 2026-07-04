"""Vendor signing tool (offline). Produces a license.key for a customer's machine hash.

    python scripts/sign_license.py <machine_hash> <expiry YYYY-MM-DD> [out=license.key]

Uses _vendor/private_key.pem. NEVER ship this script or the private key.
"""

from __future__ import annotations

import json
import os
import sys

from cryptography.hazmat.primitives import serialization

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from texttocad.licensing.rsa_verify import sign_license  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: python scripts/sign_license.py <machine_hash> <expiry> [out]")
        raise SystemExit(2)
    machine_hash_, expiry = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "license.key"
    with open(os.path.join(ROOT, "_vendor", "private_key.pem"), "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sign_license(priv, machine_hash_, expiry), f, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
