#!/usr/bin/env python3
"""Checks a running CodeCoach site from the outside, the way a visitor reaches it:

    python3 deploy/smoke-check.py https://demo.example.com

Python 3.9+ and nothing else (no packages), so it runs from a laptop or the server alike. It
verifies the certificate like a browser, then checks the security headers, readiness, the
session cookie, a written answer graded, a coding submission (judged for real if the judge is on),
that a second visitor can't see the first one's work, and, on a demo, that accounts are refused.
It makes two guest sessions, which the site deletes a day after their last use (demo settings).
Exit status 0 when every check passed. docs/GO_LIVE.md, "Check it".
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

SOLUTION = """import java.util.HashMap;
import java.util.Map;
class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            Integer j = seen.get(target - nums[i]);
            if (j != null) return new int[] {j, i};
            seen.put(nums[i], i);
        }
        throw new IllegalArgumentException("no pair");
    }
}"""
ANSWER = (
    "Last winter on a busy ward I noticed a patient's oxygen dropping during my 2 a.m. assessment. I checked "
    "his vital signs, raised the head of the bed, called the rapid response team and stayed with him. He was "
    "moved to step-down care within the hour and recovered."
)

failures = 0


def report(ok: bool, what: str) -> None:
    global failures
    failures += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + what)


class Visitor:
    """One browser: its own cookies, the site's origin on every request."""

    def __init__(self, base: str, context: ssl.SSLContext) -> None:
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.token: str | None = None

    def call(self, method: str, path: str, body: Any = None, headers: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Origin": self.base, "Accept": "application/json", **(headers or {})}
        if data is not None:
            h["Content-Type"] = "application/json"
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, resp.headers, (json.loads(raw) if raw and b"{" in raw[:1] else raw)
        except urllib.error.HTTPError as err:
            raw = err.read()
            try:
                parsed: Any = json.loads(raw)
            except ValueError:
                parsed = raw
            return err.code, err.headers, parsed

    def start_guest(self, career: str) -> bool:
        self.call("POST", "/api/v1/auth/create-anchor")
        status, headers, body = self.call("POST", "/api/v1/auth/guest", {"career_track": career})
        report(status == 201, f"a {career} guest session starts (HTTP {status})")
        if status != 201:
            return False
        self.token = body["access_token"]
        cookie = next(
            (c for c in headers.get_all("Set-Cookie") or [] if "refresh" in c.split("=", 1)[0].lower()), ""
        )
        attrs = {p.strip().lower() for p in cookie.split(";")[1:]}
        report(
            cookie.startswith("__Host-") and {"secure", "httponly", "samesite=strict"} <= attrs,
            "the session cookie is __Host-, Secure, HttpOnly and SameSite=Strict",
        )
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("site", help="the site's https address, e.g. https://demo.example.com")
    parser.add_argument("--cacert", help="trust this CA file instead of the system's (a local rehearsal)")
    args = parser.parse_args()
    base = args.site.rstrip("/")
    if not base.startswith("https://"):
        print("smoke-check: the address must start with https://", file=sys.stderr)
        return 2
    context = ssl.create_default_context(cafile=args.cacert)  # certificate always verified

    a = Visitor(base, context)
    try:
        status, headers, _ = a.call("GET", "/")
    except urllib.error.URLError as err:
        report(False, f"{base} answers over https with a valid certificate ({err.reason})")
        return 1
    report(status == 200, f"{base} answers over https with a valid certificate (HTTP {status})")
    csp = headers.get("Content-Security-Policy", "")
    report(
        "default-src 'self'" in csp and "frame-ancestors 'none'" in csp, "the Content-Security-Policy is on"
    )
    report("max-age=" in headers.get("Strict-Transport-Security", ""), "HSTS is on")
    report(headers.get("X-Frame-Options", "").upper() == "DENY", "framing is refused")
    status, _, _ = a.call("GET", "/problems/two-sum")
    report(status == 200, f"a deep link loads the app (HTTP {status})")

    status, _, ready = a.call("GET", "/health/ready")
    report(
        status == 200 and isinstance(ready, dict) and ready.get("status") == "ok",
        f"the API is ready (HTTP {status})",
    )
    status, _, caps = a.call("GET", "/api/v1/capabilities")
    caps = caps if isinstance(caps, dict) else {}
    execution = (caps.get("execution") or {}).get("state", "unknown")
    demo = bool(caps.get("demo_mode"))
    print(f"      demo mode: {demo}; code execution: {execution}; coach: {caps.get('ai_provider')}")
    status_api_docs, _, _ = a.call("GET", "/api/docs")
    report(status_api_docs == 404, "the API's docs aren't public")

    if not a.start_guest("software-engineer"):
        return 1
    status, _, body = a.call("POST", "/api/v1/auth/refresh", headers={"X-Requested-With": "codecoach"})
    report(status == 200, f"the session refreshes with its cookie (HTTP {status})")
    if status == 200:
        a.token = body["access_token"]
    status, _, sub = a.call(
        "POST",
        "/api/v1/submissions",
        {
            "problem_slug": "two-sum",
            "language": "java",
            "source_code": SOLUTION,
            "mode": "submit",
            "client_request_id": uuid.uuid4().hex,
        },
    )
    report(status in (200, 201, 202), f"a coding submission is accepted (HTTP {status})")
    sub_id = sub.get("id") if isinstance(sub, dict) else None
    if execution == "ready" and sub_id:
        started = time.time()
        while (
            str(sub.get("status")).lower() in ("queued", "running", "pending") and time.time() - started < 120
        ):
            time.sleep(1)
            _, _, sub = a.call("GET", f"/api/v1/submissions/{sub_id}")
        report(
            str(sub.get("status")).lower() == "passed",
            f"judged in the sandbox: {sub.get('status')} in {time.time() - started:.1f}s",
        )
    elif sub_id:
        print(f"      (not judged: code execution is {execution}; the submission says it wasn't run)")

    b = Visitor(base, context)
    if b.start_guest("registered-nurse"):
        status, _, graded = b.call(
            "POST",
            "/api/v1/careers/registered-nurse/questions/e-good-0/answers",
            {"answer": ANSWER, "client_request_id": uuid.uuid4().hex},
        )
        report(
            status in (200, 201) and isinstance(graded, dict) and "score" in graded,
            f"a written answer is graded (HTTP {status}, score {graded.get('score') if isinstance(graded, dict) else '?'})",
        )
        if sub_id:
            status, _, _ = b.call("GET", f"/api/v1/submissions/{sub_id}")
            report(status == 404, f"a second visitor can't see the first one's work (HTTP {status})")
    if demo:
        status, _, _ = b.call("GET", "/api/v1/demo")
        report(status == 200, f"the demo's sample learners are there (HTTP {status}; run demo-reset if 503)")
        status, _, _ = a.call(
            "POST",
            "/api/v1/auth/register",
            {"email": "smoke-check@example.com", "password": "CorrectHorse42"},
        )
        report(status == 403, f"accounts are refused on the demo (HTTP {status})")

    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) failed.'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
