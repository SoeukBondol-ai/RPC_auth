import json
import hmac
import hashlib
import base64
import time

import config


def _b64url_encode(data: dict | str) -> str:
    raw = json.dumps(data) if isinstance(data, dict) else data
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def _b64url_decode(s: str) -> dict:
    padded = s + "=" * (4 - len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def _sign(header_enc: str, payload_enc: str) -> str:
    msg = f"{header_enc}.{payload_enc}".encode()
    sig = hmac.new(config.SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


def create_token(username: str, method: str, enc_mode: str, ttl: int = 3600) -> str:
    """Issue a signed session token."""
    header = {"alg": "HS256" if enc_mode == "symmetric" else "RS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "method": method,
        "mode": enc_mode,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    h = _b64url_encode(header)
    p = _b64url_encode(payload)
    return f"{h}.{p}.{_sign(h, p)}"


def verify_token(token: str) -> dict | None:
    """Verify signature + expiry. Returns payload dict or None."""
    try:
        h, p, s = token.split(".")
        if not hmac.compare_digest(_sign(h, p), s):
            return None
        payload = _b64url_decode(p)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
