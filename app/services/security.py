import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.config import JWT_ALGORITHM, JWT_SECRET_KEY


_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        _b64url_encode(salt),
        _b64url_encode(digest),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = password_hash.split("$", 5)
        if algo != "scrypt":
            return False
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        computed = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False


def _sign(content: bytes) -> str:
    signature = hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        content,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(signature)


def create_access_token(subject: str, role: str, expires_minutes: int, extra_claims: Dict[str, Any] | None = None) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": "access",
        "iat": now,
        "exp": now + (expires_minutes * 60),
    }
    if extra_claims:
        payload.update(extra_claims)

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_and_verify_token(token: str) -> Dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Token mal formado") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Firma de token invalida")

    header = json.loads(_b64url_decode(encoded_header))
    if header.get("alg") != JWT_ALGORITHM:
        raise ValueError("Algoritmo de token no soportado")

    payload = json.loads(_b64url_decode(encoded_payload))
    now = int(time.time())
    if int(payload.get("exp", 0)) < now:
        raise ValueError("Token expirado")

    if payload.get("typ") != "access":
        raise ValueError("Tipo de token invalido")

    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def expires_at(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)
