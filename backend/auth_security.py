"""Password hashing and opaque session/CSRF tokens; no database access."""

import base64
from functools import lru_cache
import hashlib
import hmac
import re
import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from backend.auth_validation import validate_new_password

_password_hash = PasswordHash.recommended()
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_CSRF_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def hash_password(password: str) -> str:
    validate_new_password(password)
    return _password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(encoded_hash, str):
        return False
    try:
        return _password_hash.verify(password, encoded_hash)
    except (UnknownHashError, ValueError):
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """Unknown users still incur a password verification; never a real account."""
    return hash_password("DummyOnlyA1_" + secrets.token_urlsafe(32))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def decode_session_token(token: str | None) -> bytes | None:
    if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
        return None
    raw = base64.urlsafe_b64decode(token + "=")
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode().rstrip("=") != token:
        return None
    return raw


def session_digest(token: str | None) -> bytes | None:
    raw = decode_session_token(token)
    return hashlib.sha256(raw).digest() if raw is not None else None


def csrf_token(token: str) -> str:
    raw = decode_session_token(token)
    if raw is None:
        raise ValueError("INVALID_SESSION_TOKEN")
    # Session secret binds this double-submit token to one login. No additional
    # credential/session column or globally configured signing secret is needed.
    return hmac.new(raw, b"spms-auth-csrf-v1", hashlib.sha256).hexdigest()


def valid_csrf(token: str, cookie: str | None, header: str | None) -> bool:
    if not isinstance(cookie, str) or not isinstance(header, str):
        return False
    if not _CSRF_PATTERN.fullmatch(cookie) or not _CSRF_PATTERN.fullmatch(header):
        return False
    return hmac.compare_digest(cookie, header) and hmac.compare_digest(header, csrf_token(token))
