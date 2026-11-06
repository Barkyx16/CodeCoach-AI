"""Authentication primitives: password hashing and JWT access tokens.

Passwords
    Hashed with Argon2id (winner of the Password Hashing Competition, OWASP's first choice).
    The hash string embeds its own salt and cost parameters, so parameters can be raised later
    and old hashes are transparently upgraded on the next successful login (needs_rehash).

Access tokens
    Short-lived HS256 JWTs. Claims: sub (user id), ver (user.token_version), iat, exp, iss,
    typ. Logging out or changing a password increments token_version, which invalidates every
    token issued before it, without a server-side token table.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # Argon2id with the library's current recommended parameters
ALGORITHM = "HS256"
ISSUER = "codecoach-api"

# A real hash of a random string: verifying against it when the email is unknown keeps
# login timing the same whether or not the account exists (prevents user enumeration).
_DUMMY_HASH = _hasher.hash("codecoach-timing-equalizer")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def issue_access_token(
    secret: str, *, user_id: str, token_version: int, ttl: timedelta
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires = now + ttl
    claims = {
        "sub": user_id,
        "ver": token_version,
        "iat": now,
        "exp": expires,
        "iss": ISSUER,
        "typ": "access",
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM), expires


def decode_access_token(secret: str | Sequence[str], token: str) -> dict | None:
    """Return the verified claims, or None for any invalid, expired or tampered token.

    `secret` may be several keys (the current one first, then ones being rotated out): a token
    signed by any of them is accepted. Only the current key ever signs."""
    keys = [secret] if isinstance(secret, str) else list(secret)
    claims = None
    for key in keys:
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                issuer=ISSUER,
                options={"require": ["sub", "exp", "iat", "iss"]},
            )
            break
        except jwt.InvalidSignatureError:
            continue  # maybe signed with an older key
        except jwt.PyJWTError:
            return None  # expired, malformed, wrong issuer: no other key changes that
    if claims is None:
        return None
    if claims.get("typ") != "access" or not isinstance(claims.get("ver"), int):
        return None
    return claims
