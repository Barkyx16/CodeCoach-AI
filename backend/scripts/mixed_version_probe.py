"""Run one version of the backend code against a disposable database at some schema revision.

    python scripts/mixed_version_probe.py --app-root <checkout>/backend <database url>

Used for the mixed-version matrix (docs/RELEASE_READINESS.md): old code against the expanded
schema, new code against the previous schema. The database must be a local
``codecoach_rehearsal_*`` one, already migrated to the revision under test (this script never
migrates, drops or resets anything; it adds one synthetic account and its answers). Prints what
each request returned and which response fields were present, never answer text or tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

LONG = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-root", type=Path, required=True)
    ap.add_argument("database_url")
    a = ap.parse_args()
    from sqlalchemy.engine import make_url

    u = make_url(a.database_url)
    if not (u.database or "").startswith("codecoach_rehearsal_") or u.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("refused: only a local database named codecoach_rehearsal_* may be used")
    sys.path.insert(0, str(a.app_root.resolve()))
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        environment="test",
        database_url=a.database_url,
        secret_key="rehearsal-secret-key-that-is-long-enough-0123456789",
        ai_provider="offline",
        auth_rate_limit_per_minute=1000,
        _env_file=None,
    )
    out: dict = {"app_root": str(a.app_root), "steps": []}
    with TestClient(create_app(settings), raise_server_exceptions=False) as c:
        email = f"probe-{uuid.uuid4().hex[:8]}@example.com"
        r = c.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "CorrectHorse42", "display_name": "Probe"},
        )
        token = r.json().get("access_token") if r.status_code < 300 else None
        out["steps"].append({"step": "register", "status": r.status_code})
        h = {"Authorization": f"Bearer {token}"} if token else {}
        qs = c.get("/api/v1/careers/registered-nurse/questions", headers=h, params={"page_size": 1})
        qid = qs.json()["items"][0]["id"] if qs.status_code == 200 else "unknown"
        url = f"/api/v1/careers/registered-nurse/questions/{qid}/answers"
        key = f"op-probe-{uuid.uuid4().hex[:12]}"
        for name, body in (
            ("save without a key", {"answer": LONG}),
            ("save with a key", {"answer": LONG, "client_request_id": key}),
            ("resend with the same key", {"answer": LONG, "client_request_id": key}),
        ):
            r = c.post(url, headers=h, json=body)
            out["steps"].append(
                {
                    "step": name,
                    "status": r.status_code,
                    "replayed": r.headers.get("Idempotent-Replayed"),
                    "fields": sorted(r.json())
                    if r.status_code < 300
                    else r.json().get("error", {}).get("code"),
                }
            )
        before = c.get(url, headers=h).json() if token else []
        r = c.post(
            f"{url}/keyed", headers=h, json={"answer": LONG + " Keyed.", "client_request_id": key + "-p"}
        )
        after = c.get(url, headers=h).json() if token else []
        out["steps"].append(
            {
                "step": "protected route",
                "status": r.status_code,
                "saved": len(after) - len(before)
                if isinstance(after, list) and isinstance(before, list)
                else None,
            }
        )
        r = c.get(url, headers=h)
        out["steps"].append(
            {
                "step": "list answers",
                "status": r.status_code,
                "count": len(r.json()) if r.status_code == 200 else None,
            }
        )
        r = c.get("/api/v1/careers/registered-nurse/questions", headers=h, params={"page_size": 200})
        item = (
            next((q for q in r.json().get("items", []) if q["id"] == qid), {}) if r.status_code == 200 else {}
        )
        out["steps"].append(
            {
                "step": "question summary",
                "status": r.status_code,
                "fields": sorted(k for k in item if "score" in k),
            }
        )
        r = c.get("/health/ready")
        out["steps"].append({"step": "readiness", "status": r.status_code, "checks": r.json().get("checks")})
        r = c.get("/api/v1/capabilities")
        out["steps"].append(
            {
                "step": "capabilities",
                "status": r.status_code,
                "answer_request_keys": r.json().get("answer_request_keys"),
            }
        )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
