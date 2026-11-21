"""What a request key stands for (Volume 8, prompt 2; docs/RECOVERY.md "What a key identifies").

A request key (`client_request_id`) lets a request sent again after a lost reply get the first
result back instead of doing the work twice. A key identifies one account's one intent: the
operation, its target, and the validated input that decides the result. The same key with a
different intent is refused with 409 `idempotency_key_reused`, never answered with the old
result and never executed.

The fingerprint is made here, on the server, from validated input: never a browser-supplied
hash. Only its digest is stored, beside the record it made; it isn't shown in responses,
diagnostics or exports, and it isn't the key (raw content is never a deduplication key).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.errors import ConflictError

VERSION = "v1"


def fingerprint(operation: str, payload: Any) -> str:
    """A digest of the operation and its canonical input (sorted keys, no whitespace)."""
    text = json.dumps({"op": operation, "input": payload}, sort_keys=True, separators=(",", ":"), default=str)
    return f"{VERSION}:" + hashlib.sha256(text.encode()).hexdigest()


def same(stored: str | None, fresh: str) -> bool:
    """Whether a stored fingerprint matches. A record made before fingerprints were kept has
    none: it is matched on what the caller checked before (its target), as it always was."""
    return stored is None or hmac.compare_digest(stored, fresh)


def reused(what: str = "request") -> ConflictError:
    """The one refusal for a key sent with a different intent. It says nothing about what the
    key made the first time (no id, content, time or fingerprint), so it reveals nothing even
    if the key wasn't the caller's to begin with."""
    return ConflictError(
        f"This request key was already used for a different {what}. Send it with a new key.",
        code="idempotency_key_reused",
    )


def check(stored: str | None, fresh: str, what: str = "request") -> None:
    if not same(stored, fresh):
        raise reused(what)
