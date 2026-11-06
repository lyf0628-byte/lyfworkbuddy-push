"""鉴权：pbkdf2 口令哈希 + 手写 HS256 JWT（零第三方依赖）。

刻意不引入 PyJWT：JWT 的 HS256 只有 base64 + hmac，手写几十行即可，
减少依赖面（对应需求「依赖极少」的工程约束）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from .config import settings

_PBKDF2_ITERATIONS = 120_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or base64.b64encode(hashlib.sha256(str(time.time_ns()).encode()).digest()[:16]).decode()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, dk_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = base64.b64decode(dk_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(candidate, dk)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- JWT

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_token(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    body = {
        **payload,
        "iat": now,
        "exp": now + settings.jwt_ttl_hours * 3600,
    }
    seg1 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    seg2 = _b64url(json.dumps(body, separators=(",", ":")).encode())
    signing_input = f"{seg1}.{seg2}"
    sig = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        seg1, seg2, seg3 = token.split(".")
        signing_input = f"{seg1}.{seg2}"
        expected = hmac.new(settings.jwt_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        got = _b64url_decode(seg3)
        if not hmac.compare_digest(expected, got):
            return None
        body = json.loads(_b64url_decode(seg2))
        if body.get("exp", 0) < time.time():
            return None
        return body
    except Exception:  # noqa: BLE001
        return None
