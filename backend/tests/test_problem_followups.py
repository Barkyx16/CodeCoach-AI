"""A reviewed follow-up problem (Volume 14, prompt 10; docs/FOLLOW_UPS.md, "Coding problems"):
offered only after a judged submission of the first problem passed (never after a run), only while
the second hasn't been attempted, and not again once dismissed (on any device); a submission made
from the offer stores its link once, to the learner's own passed submission only; each verdict is
its own, never compared; the link is in the export. The pair list is reviewed content, checked by
the content gate. The judge isn't run here: verdicts are written as the worker writes them.
Synthetic data only."""

from datetime import UTC, datetime

from app.content.problem_followups import PAIRS, ProblemFollowUp, problems
from app.models import ExecutionResult, Submission, SubmissionMode, SubmissionStatus
from tests.test_submission_comparisons import BETTER, CODE, coder, detail, judge

SORTED = "class Solution { public int[] twoSumSorted(int[] nums, int target) { return new int[0]; } }"
FU = "/api/v1/problems/two-sum/follow-ups"


def submit(client, h, slug="two-sum", code=CODE, mode="submit", follows=None):
    body = {"problem_slug": slug, "source_code": code, "mode": mode}
    if follows:
        body["follows_up_submission_id"] = follows
    return client.post("/api/v1/submissions", headers=h, json=body)


def passed_two_sum(client, h):
    first = submit(client, h, code=BETTER).json()["id"]
    judge(client, first, SubmissionStatus.PASSED, 7)
    return first


def run_passed(client, like):
    """A run of the same problem, by the same learner, that passed every public test."""
    with client.app.state.session_factory() as db:
        src = db.get(Submission, like)
        run = Submission(
            user_id=src.user_id,
            problem_id=src.problem_id,
            language=src.language,
            source_code=BETTER,
            mode=SubmissionMode.RUN,
            status=SubmissionStatus.PASSED,
            judged_at=datetime.now(UTC),
        )
        db.add(run)
        db.flush()
        db.add(ExecutionResult(submission_id=run.id, passed_count=2, total_count=2, public_results=[]))
        db.commit()


def offer(client, h, url=FU):
    r = client.get(url, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_offered_only_after_a_judged_pass_and_never_after_a_run_or_a_failure(client):
    h = coder(client)
    assert offer(client, h)["status"] == "not_yet"
    failed = submit(client, h).json()["id"]
    judge(client, failed, SubmissionStatus.FAILED, 2)
    assert offer(client, h)["status"] == "not_yet"
    # A run that passed the public tests isn't a judged submission (written as the worker would: runs
    # need the sandbox, which isn't on here).
    run_passed(client, failed)
    assert offer(client, h)["status"] == "not_yet"
    first = passed_two_sum(client, h)
    got = offer(client, h)
    assert got["status"] == "offered"
    [o] = got["offers"]
    assert (o["slug"], o["title"], o["from_submission_id"]) == (
        "two-sum-sorted",
        "Two Sum in a Sorted Array",
        first,
    )
    assert o["shares"] == "Finding the two values that add up to a target"
    assert o["exposure"] == "Not previously attempted in this app"
    assert "passing it doesn't by itself show that anything was learned" in got["message"]


def test_not_offered_once_the_second_problem_was_attempted(client):
    h = coder(client)
    passed_two_sum(client, h)
    submit(client, h, slug="two-sum-sorted", code=SORTED)  # tried it on its own already
    got = offer(client, h)
    assert got["status"] == "done" and got["offers"] == []


def test_a_follow_up_stores_its_link_once_keeps_its_own_verdict_and_is_listed_not_combined(client):
    h = coder(client)
    first = passed_two_sum(client, h)
    r = submit(client, h, slug="two-sum-sorted", code=SORTED, follows=first)
    assert r.status_code == 202, r.text
    fu = r.json()["id"]
    judge(client, fu, SubmissionStatus.FAILED, 1, 6)
    page = detail(client, h, fu)
    assert page["follows_up"]["submission_id"] == first and page["follows_up"]["problem_slug"] == "two-sum"
    assert page["follows_up"]["text"] == (
        "A follow-up to Two Sum, a different problem. Its own verdict, not combined with that problem's or "
        "compared with it."
    )
    assert page["compared"] is None  # never set beside a different problem's verdict
    listed = offer(client, h)
    assert listed["status"] == "done"  # attempted now, so not offered again
    [done] = listed["answered"]
    assert (done["submission_id"], done["status"], done["passed_count"], done["total_count"]) == (
        fu,
        "FAILED",
        1,
        6,
    )
    assert detail(client, h, first)["status"] == "PASSED"  # the first verdict untouched
    # The export carries the link.
    doc = client.get("/api/v1/me/export", headers=h).json()
    assert {s["id"]: s["follows_up_submission_id"] for s in doc["submissions"]}[fu] == first


def test_a_link_to_a_failure_another_account_or_an_unrelated_problem_is_refused(client):
    h = coder(client)
    failed = submit(client, h).json()["id"]
    judge(client, failed, SubmissionStatus.FAILED, 2)
    r = submit(client, h, slug="two-sum-sorted", code=SORTED, follows=failed)
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_follow_up"
    first = passed_two_sum(client, h)
    other = coder(client, "other@example.com")
    r = submit(client, other, slug="two-sum-sorted", code=SORTED, follows=first)
    assert r.status_code == 404  # another account's submission: not found
    r = submit(client, h, slug="valid-anagram", code="class Solution {}", follows=first)
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_follow_up"
    assert offer(client, other)["status"] == "not_yet"  # someone else's pass offers them nothing


def test_dismissed_it_stays_dismissed_on_another_device(client):
    h = coder(client)
    passed_two_sum(client, h)
    r = client.post(f"{FU}/two-sum-sorted/dismiss", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "done"
    from tests.conftest import auth_headers

    again = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "CorrectHorse42"})
    assert again.status_code == 200, again.text
    other_device = auth_headers(again.json())
    assert offer(client, other_device)["status"] == "done"
    assert client.post(f"{FU}/valid-anagram/dismiss", headers=h).status_code == 404  # no such pair


def test_a_problem_with_no_reviewed_pair_offers_nothing(client):
    h = coder(client)
    got = offer(client, h, "/api/v1/problems/merge-intervals/follow-ups")
    assert got["status"] == "none" and got["offers"] == []


def test_the_content_gate_checks_every_pair():
    real = {p.from_slug for p in PAIRS} | {p.to_slug for p in PAIRS}
    assert problems(PAIRS, lambda s: s in real) == []
    bad = (
        ProblemFollowUp("two-sum", "two-sum", "x", "y", "Reviewed today"),
        ProblemFollowUp("two-sum", "no-such-problem", "x", "y", "Reviewed today"),
        ProblemFollowUp("two-sum", "three-sum", "", "y", "Reviewed today"),
        ProblemFollowUp("two-sum", "valid-anagram", "x", "y", "Draft"),
        ProblemFollowUp("two-sum", "valid-anagram", "x", "y", "Reviewed today"),
    )
    found = problems(bad, lambda s: s in real | {"three-sum", "valid-anagram"})
    assert "problem follow-up two-sum -> two-sum: a problem can't follow itself" in found
    assert any("'no-such-problem' isn't in the bank" in f for f in found)
    assert any("needs the idea they share" in f for f in found)
    assert any(f.endswith("not reviewed") for f in found)
    assert any(f.endswith("listed twice") for f in found)
