"""A lesson drafted here says it's a draft wherever it's shown (Volume 18, prompt 8; docs/LEARN_CONTENT.md,
rule 3). "Fixing code from a failing test" was written in this repository (Volume 17, prompt 5) and
nobody has reviewed it yet, so it's a generated draft, naming no reviewer: on its own page, in the
Learn list, beside its "Learn first" link on each exercise (each lesson link carries its review
status, prerequisites too), and in the plan's reason when the plan suggests it. A reviewed lesson
reads as before. Synthetic data only."""

from __future__ import annotations

from app.learn import UNIT_INDEX
from app.models import SubmissionStatus
from tests.test_plan_code_evidence import LAB, coder, judged, plan
from tests.test_plan_lesson_evidence import weak_handoffs
from tests.test_plan_updates import nurse

DRAFT = "se-failing-test"
NOTE = " It's a generated draft, not reviewed yet."


def test_the_lesson_drafted_here_is_a_draft_naming_no_reviewer(client):
    u = UNIT_INDEX[DRAFT]
    assert u.review.status == "generated_draft"
    assert "project author" not in u.review.by and "Not yet reviewed" in u.review.note
    page = client.get(f"/api/v1/learn/units/{DRAFT}").json()
    assert page["review"]["status"] == "generated_draft" and page["review_status"] == "generated_draft"
    listed = client.get("/api/v1/learn", params={"track": "software-engineer"}).json()["units"]
    assert {x["id"]: x["review_status"] for x in listed}[DRAFT] == "generated_draft"


def test_every_lesson_link_carries_its_review_status(client):
    for slug in ("debug-coldest-day", "debug-count-at-most", "debug-palindrome-sentence"):
        related = client.get("/api/v1/learn/related", params={"problem_slug": slug}).json()
        assert {"id": DRAFT, "title": UNIT_INDEX[DRAFT].title, "review_status": "generated_draft"} in related
    reviewed = client.get("/api/v1/learn/related", params={"problem_slug": "two-sum"}).json()
    assert [x["review_status"] for x in reviewed if x["id"] == "se-hash-map-lookup"] == ["author_reviewed"]
    # Prerequisites are lesson links too.
    prio = client.get("/api/v1/learn/units/rn-prioritization").json()
    assert all(p["review_status"] == UNIT_INDEX[p["id"]].review.status for p in prio["prerequisites"])
    assert prio["prerequisites"]


def test_the_plan_says_a_suggested_draft_is_a_draft(client):
    h = coder(client)
    judged(client, h, LAB, SubmissionStatus.FAILED)
    [item] = [i for i in plan(client, h)["items"] if i["kind"] == "learn"]
    assert item["href"] == f"/learn/{DRAFT}" and item["reason"].endswith(NOTE)


def test_a_reviewed_lesson_reads_as_before(client):
    h = nurse(client)
    weak_handoffs(client, h)
    [item] = [i for i in plan(client, h, track="registered-nurse")["items"] if i["kind"] == "learn"]
    assert item["href"] == "/learn/rn-sbar-handoff" and "draft" not in item["reason"]
    assert item["reason"].startswith("A ") and item["reason"].endswith(".")
