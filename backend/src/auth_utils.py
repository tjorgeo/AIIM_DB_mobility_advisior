"""
Passwort-Hashing ohne Zusatz-Dependency (nur Python-Stdlib, PBKDF2-HMAC-SHA256).

Ablage: backend/src/auth_utils.py

Format des gespeicherten Hashes:
    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

Wird von register_endpoint.py (hash_password beim Anlegen) und vom
/api/login-Handler (verify_password beim Anmelden) genutzt.
"""

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Erzeugt einen salted PBKDF2-Hash als speicherbaren String."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Prüft ein Klartext-Passwort gegen einen gespeicherten Hash (timing-safe)."""
    if not stored:
        return False
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False