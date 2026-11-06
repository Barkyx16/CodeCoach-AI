"""Response caching for the public catalogue, and "never store" for everything else.

Three rules, applied to every API response that hasn't set its own Cache-Control:

1. **Shared catalogue reads** (the same for everyone: careers, problem lists, topics, lessons,
   scenarios, interview formats) are kept in a small in-process cache for `TTL_S` seconds, so
   repeated reads skip the database and the serialising. Browsers and proxies may keep them for
   `TTL_S` too (`public, max-age`), with an ETag so a refresh after that costs a 304, not a body.
2. **Personalised catalogue reads** (a question list or problem page shows your progress when
   you're signed in) get the same treatment only when the request carries no Authorization
   header; signed-in requests always reach the route. `Vary: Authorization` keeps any shared
   cache from mixing the two.
3. **Everything else** (all private data, auth, health) is `Cache-Control: no-store`: no
   browser, proxy or CDN may keep a copy.

The in-process cache key includes the published-content fingerprint (app/content/state.py), so
a correction or retirement is served at once in this process and within its refresh interval
in the others. Only 200 responses under `MAX_BODY` bytes are kept; at most `MAX_ENTRIES`.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

import anyio
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.content import state as content_state

TTL_S = 60
MAX_ENTRIES = 512
MAX_BODY = 512 * 1024

# Same answer for every caller, signed in or not.
SHARED = [
    r"/api/v1/careers",
    r"/api/v1/problems",
    r"/api/v1/problems/counts",
    r"/api/v1/topics",
    r"/api/v1/careers/[^/]+/questions/counts",
    r"/api/v1/careers/[^/]+/explore",
    r"/api/v1/careers/[^/]+/questions/[^/]+/criteria",
    r"/api/v1/careers/[^/]+/questions/[^/]+/versions/\d+",
    r"/api/v1/learn",
    r"/api/v1/learn/related",
    r"/api/v1/learn/units/[^/]+",
    r"/api/v1/scenarios",
    r"/api/v1/scenarios/[^/]+",
    r"/api/v1/interviews/formats",
]
# Public, but personalised for a signed-in caller: cached only for anonymous requests.
ANONYMOUS_ONLY = [
    r"/api/v1/problems/[^/]+",
    r"/api/v1/careers/[^/]+/questions",
    r"/api/v1/careers/[^/]+/questions/[^/]+",
]
_SHARED = re.compile("^(?:" + "|".join(SHARED) + ")$")
_ANONYMOUS = re.compile("^(?:" + "|".join(ANONYMOUS_ONLY) + ")$")


@dataclass
class Entry:
    body: bytes
    headers: list[tuple[bytes, bytes]]
    etag: bytes
    expires: float
    route: object = None  # the matched route, so logs and metrics still name it on a hit


class ResponseCache:
    def __init__(self) -> None:
        self._entries: OrderedDict[tuple, Entry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: tuple) -> Entry | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or entry.expires <= time.monotonic():
                self._entries.pop(key, None)
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return entry

    def put(self, key: tuple, entry: Entry) -> None:
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > MAX_ENTRIES:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def _header(scope: Scope, name: bytes) -> bytes | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v
    return None


def _has(headers: list[tuple[bytes, bytes]], name: bytes) -> bool:
    return any(k.lower() == name for k, _ in headers)


def _etag(body: bytes) -> bytes:
    return b'W/"' + hashlib.sha256(body).hexdigest()[:20].encode() + b'"'


def _matches(if_none_match: bytes | None, etag: bytes) -> bool:
    if not if_none_match:
        return False
    tags = [t.strip() for t in if_none_match.split(b",")]
    return b"*" in tags or etag in tags or etag.removeprefix(b"W/") in tags


class CacheMiddleware:
    """Pure ASGI (no BaseHTTPMiddleware), innermost: the request-context middleware outside it
    still logs, traces and counts every request, cached or not."""

    def __init__(self, app: ASGIApp, cache: ResponseCache | None = None) -> None:
        self.app = app
        self.cache = cache or ResponseCache()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        method = scope["method"]
        signed_in = _header(scope, b"authorization") is not None
        cacheable = method in ("GET", "HEAD") and (
            _SHARED.match(path) is not None or (_ANONYMOUS.match(path) is not None and not signed_in)
        )
        if not cacheable:
            await self.app(scope, receive, _no_store(send))
            return

        vary = _ANONYMOUS.match(path) is not None
        query = scope.get("query_string", b"")
        snap = content_state.current()
        if time.monotonic() - snap.loaded_at > content_state.MAX_AGE_S:
            # Older than its refresh interval: it may be behind a change made on another replica.
            # Refresh it (one small query, off the event loop) before trusting the cache key.
            snap = await anyio.to_thread.run_sync(_refresh_content_state, scope)
        entry = self.cache.get((method, path, query, snap.fingerprint))
        if entry is not None:
            if entry.route is not None:
                scope["route"] = entry.route
            await _replay(entry, _header(scope, b"if-none-match"), send, head=method == "HEAD")
            return

        captured: dict = {"status": 0, "headers": [], "body": bytearray(), "too_big": False}

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = list(message.get("headers", []))
                return
            if message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")
                if len(captured["body"]) > MAX_BODY:
                    captured["too_big"] = True
                if message.get("more_body"):
                    return
            # (any other message type passes through unchanged)

        await self.app(scope, receive, capture)
        body = bytes(captured["body"])
        headers = [(k, v) for k, v in captured["headers"] if k.lower() not in (b"content-length",)]
        uncacheable = _has(headers, b"cache-control") or _has(headers, b"set-cookie")
        if captured["status"] != 200 or captured["too_big"] or uncacheable:
            if not _has(headers, b"cache-control"):
                headers.append((b"cache-control", b"no-store"))
            headers.append((b"content-length", str(len(body)).encode()))
            await send({"type": "http.response.start", "status": captured["status"], "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return
        etag = _etag(body)
        headers += [(b"cache-control", f"public, max-age={TTL_S}".encode()), (b"etag", etag)]
        if vary:
            headers.append((b"vary", b"Authorization"))
        entry = Entry(
            body=body, headers=headers, etag=etag, expires=time.monotonic() + TTL_S, route=scope.get("route")
        )
        # Keyed by the snapshot the route just answered from (it refreshes it on the way in).
        self.cache.put((method, path, query, content_state.current().fingerprint), entry)
        await _replay(entry, _header(scope, b"if-none-match"), send, head=method == "HEAD", fresh=True)


async def _replay(
    entry: Entry, if_none_match: bytes | None, send: Send, *, head: bool, fresh: bool = False
) -> None:
    headers = list(entry.headers) + [(b"x-cache", b"miss" if fresh else b"hit")]
    if _matches(if_none_match, entry.etag):
        await send({"type": "http.response.start", "status": 304, "headers": headers})
        await send({"type": "http.response.body", "body": b""})
        return
    headers.append((b"content-length", str(len(entry.body)).encode()))
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": b"" if head else entry.body})


def _refresh_content_state(scope: Scope) -> content_state.Snapshot:
    with scope["app"].state.session_factory() as db:
        return content_state.refresh(db)


def _no_store(send: Send) -> Send:
    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = list(message.get("headers", []))
            if not _has(headers, b"cache-control"):
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
        await send(message)

    return wrapped
