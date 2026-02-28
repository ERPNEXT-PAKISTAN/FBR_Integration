import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Tuple


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def sign_payload(payload: Dict[str, Any], secret: str) -> Tuple[str, str]:
    """
    Returns (payload_b64url, sig_b64url)
    """
    msg = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return b64url_encode(msg), b64url_encode(sig)


def verify_signed(payload_b64url: str, sig_b64url: str, secret: str) -> bool:
    msg = b64url_decode(payload_b64url)
    sig = b64url_decode(sig_b64url)
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return hmac.compare_digest(sig, expected)