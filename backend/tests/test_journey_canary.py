"""The preparation journey's API path with every log and trace kept (Volume 12, prompt 10;
docs/PREPARATION_JOURNEY.md): a secret-shaped canary typed by the learner (in a story, an answer, a
target's posting, a kit's notes and a search) never reaches a log record or a trace span, including
the access log, at the most verbose level. The browser journey's server logs only warnings, so this is
where traces are checked. Synthetic data only."""

from __future__ import annotations

import json
import logging

from tests.conftest import auth_headers, register

CANARY = "CANARY-journey-7f3a9-not-a-real-secret"
TRACK = "registered-nurse"
JD = f"""Registered Nurse - Medical Ward ({CANARY})
Requirements:
- Patient assessment and triage
- Infection control
- Patient education
Responsibilities:
- Perform patient assessment and triage for incoming patients
- Administer medications and monitor patient responses"""
STRONG = (
    "Last winter, while I was working nights, a patient's oxygen dropped during my 2 a.m. patient assessment. "
    "I was responsible for five patients, so I moved fast. I checked his vital signs again and started oxygen "
    "per protocol. I called the rapid response team and asked the charge nurse to cover my other patients. I "
    "updated the doctor and documented everything. As a result, he was stable within 30 minutes, and I learned "
    f"to escalate early. ({CANARY})"
)


def rendered(record: logging.LogRecord) -> str:
    """Everything a handler could write for this record: the message, its arguments and every extra
    field (the trace spans' attributes travel as extras)."""
    return record.getMessage() + " " + json.dumps(record.__dict__, default=str)


def test_the_canary_never_reaches_a_log_or_a_trace(client, caplog):
    caplog.set_level(logging.DEBUG)
    h = auth_headers(register(client, career_track=TRACK))
    t = client.post("/api/v1/targets", headers=h, json={"title": "Ward nurse", "description": JD}).json()
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "questions", **t["targeted_session"]["round"]}
    ).json()
    for i in range(3):
        r = client.post(
            f"/api/v1/interviews/{iv['id']}/answers",
            headers=h,
            json={"question_index": i, "answer": STRONG, "source": "typed"},
        )
        assert r.status_code == 200, r.text
    review = client.get(f"/api/v1/interviews/{iv['id']}/review", headers=h).json()
    key = review["improvements"][0]["key"]
    action = client.post(
        "/api/v1/me/actions", headers=h, json={"source": {"interview_id": iv["id"], "key": key}}
    )
    assert action.status_code in (200, 201), action.text
    story = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Two call lights", "situation": f"Night shift {CANARY}"},
    ).json()
    app = client.post(
        "/api/v1/me/applications",
        headers=h,
        json={"employer": "Synthetic Hospital", "role_title": "Ward nurse"},
    ).json()
    ev = client.post(
        f"/api/v1/me/applications/{app['id']}/events", headers=h, json={"title": "Panel interview"}
    ).json()["events"][0]
    kit = client.put(
        f"/api/v1/me/applications/{app['id']}/events/{ev['id']}/kit",
        headers=h,
        json={"story_ids": [story["id"]], "notes": f"Bring badge ({CANARY})"},
    )
    assert kit.status_code == 200, kit.text
    follow_up = client.post(
        f"/api/v1/careers/{TRACK}/questions/e-accuracy-1/answers", headers=h, json={"answer": STRONG}
    )
    assert follow_up.status_code == 201, follow_up.text
    # A search with the canary in the query string: the access log keeps the path, never the query.
    assert client.get(f"/api/v1/me/notes?q={CANARY}", headers=h).status_code == 200

    # The server's records: the test client's own request log (httpx, on this side of the wire) isn't
    # the server's and would show the URL it sent.
    records = [r for r in caplog.records if not r.name.startswith(("httpx", "httpcore"))]
    assert any(r.name == "codecoach.trace" for r in records)  # traces were on, and are checked
    assert any(r.name == "codecoach.access" for r in records)
    leaked = [f"{r.name}: {r.getMessage()[:80]}" for r in records if CANARY in rendered(r)]
    assert leaked == []
