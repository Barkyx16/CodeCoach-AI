"""An interview closes when its time runs out, not only when it's next read (Volume 17, prompt 1;
docs/COACH_CONTEXT.md, "When time runs out"). Housekeeping's interviews_expired step closes each
in-progress interview past its deadline exactly as a read would: the same reason, the same
feedback-read record, a coding interview scored once with the learner's coaching (a fake provider
here: nothing leaves the machine). It's bounded per pass, oldest deadline first; a read racing it
closes the interview once; one not yet due is untouched; an export taken after a pass shows it ended.
And a check before time ran out now says what changed after it: the lines added (by number, read from
the code the interview keeps) and removed, or how many messages were sent after it, with only line
digests kept with the check. Synthetic data only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db import rls
from app.jobs import JobsRunner, close_interviews, housekeeping
from app.models import InterviewStatus, PracticeSession
from app.services.interviews import close_overdue
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import Recording, say
from tests.test_feedback_check import checked
from tests.test_feedback_read import expire, get
from tests.test_question_rounds import start as start_round


def coding(client, email="ada@example.com", rec=None):
    h = auth_headers(register(client, email=email))
    client.app.state.ai_provider = rec or getattr(client.app.state, "ai_provider", None) or Recording()
    r = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "coding", "problem_slug": "two-sum", "duration_minutes": 15},
    )
    assert r.status_code == 201, r.text
    return h, r.json()


def sweep(client, **kw) -> int:
    """One pass, as the jobs runner makes it: worker-scoped sessions, the app's provider."""
    factory = rls.scoped(client.app.state.session_factory, rls.WORKER)
    return close_overdue(factory, client.app.state.settings, client.app.state.ai_provider, **kw)


def stored(client, iv_id) -> PracticeSession:
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv_id)
        db.expunge(s)
        return s


def test_a_pass_closes_an_interview_past_its_time_as_a_read_would(client):
    rec = Recording()
    h1, by_sweep = coding(client, rec=rec)
    h2, by_read = coding(client, email="grace@example.com", rec=rec)
    for h, iv in ((h1, by_sweep), (h2, by_read)):
        assert say(client, h, iv, code=CODE).status_code == 200
        expire(client, iv["id"])
    assert sweep(client) == 2  # both are due; nobody has read either
    s = stored(client, by_sweep["id"])
    assert s.status == InterviewStatus.EXPIRED and s.ended_at is not None
    assert len(rec.evaluations) == 2  # each scored once, with the coach, as a read would
    # The one closed by the pass reads the same as one closed by a read, but for when.
    with client.app.state.session_factory() as db:  # reopen the second, to close it by a read
        db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == by_read["id"])
            .values(status=InterviewStatus.IN_PROGRESS, ended_at=None, evaluation=None)
        )
        db.commit()
    a, b = get(client, h1, by_sweep["id"]), get(client, h2, by_read["id"])
    assert a["status"] == b["status"] == "expired"
    ra, rb = a["feedback_read"], b["feedback_read"]
    # (The fingerprint covers each interview's own material, so it's theirs alone.)
    assert {k: v for k, v in ra.items() if k != "fingerprint"} == {
        k: v for k, v in rb.items() if k != "fingerprint"
    }
    assert ra["ending"] == "time_expired" and ra["text"] == (
        "You didn't check this before it was scored: time ran out."
    )


def test_one_not_yet_due_is_untouched(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    assert sweep(client) == 0
    assert stored(client, iv["id"]).status == InterviewStatus.IN_PROGRESS
    assert get(client, h, iv["id"])["status"] == "in_progress"


def test_a_read_and_a_pass_close_it_once(client):
    rec = Recording()
    h, iv = coding(client, rec=rec)
    say(client, h, iv, code=CODE)
    expire(client, iv["id"])
    assert get(client, h, iv["id"])["status"] == "expired"  # the read closed it
    assert sweep(client) == 0 and len(rec.evaluations) == 1
    h2, iv2 = coding(client, email="grace@example.com", rec=rec)
    say(client, h2, iv2, code=CODE)
    expire(client, iv2["id"])
    assert sweep(client) == 1 and sweep(client) == 0  # the pass closed it; a second finds nothing
    assert get(client, h2, iv2["id"])["status"] == "expired" and len(rec.evaluations) == 2


def test_a_pass_is_bounded_oldest_deadline_first(client):
    rec = Recording()
    ids = []
    for n, email in enumerate(["a@example.com", "b@example.com", "c@example.com"]):
        h, iv = coding(client, email=email, rec=rec)
        with client.app.state.session_factory() as db:  # deadlines 3, 2 and 1 minutes ago
            db.get(PracticeSession, iv["id"]).deadline_at = datetime.now(UTC) - timedelta(minutes=3 - n)
            db.commit()
        ids.append(iv["id"])
    assert sweep(client, limit=2) == 2
    states = [stored(client, i).status for i in ids]
    assert states == [InterviewStatus.EXPIRED, InterviewStatus.EXPIRED, InterviewStatus.IN_PROGRESS]
    assert sweep(client, limit=2) == 1  # the next pass takes the rest
    assert stored(client, ids[2]).status == InterviewStatus.EXPIRED


def test_a_career_round_past_its_time_is_closed_without_the_coach(client):
    rec = Recording()
    client.app.state.ai_provider = rec
    h = auth_headers(register(client, email="nurse@example.com", career_track="registered-nurse"))
    r = start_round(client, h)
    assert r.status_code == 201, r.text
    expire(client, r.json()["id"])
    assert sweep(client) == 1 and rec.evaluations == []
    got = get(client, h, r.json()["id"])
    assert got["status"] == "expired"
    assert got["feedback_read"]["text"].startswith("Time ran out, so it was scored from what you'd answered.")


def test_an_export_after_a_pass_shows_it_ended(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    expire(client, iv["id"])
    before = client.get("/api/v1/me/export", headers=h).json()
    # Exporting doesn't read the interview the way its page does: it still showed running.
    assert next(i for i in before["interviews"] if i["id"] == iv["id"])["status"] == "in_progress"
    sweep(client)
    after = client.get("/api/v1/me/export", headers=h).json()
    row = next(i for i in after["interviews"] if i["id"] == iv["id"])
    assert row["status"] == "expired" and row["feedback_read"]["ending"] == "time_expired"


def test_housekeeping_runs_the_step_and_the_runner_runs_it_every_minute(client):
    h, iv = coding(client)
    expire(client, iv["id"])
    done = housekeeping(
        client.app.state.session_factory, client.app.state.settings, provider=client.app.state.ai_provider
    )
    assert done["interviews_expired"] == 1
    assert close_interviews(
        client.app.state.session_factory, client.app.state.settings, client.app.state.ai_provider
    ) == {"interviews_expired": 0}
    now = [1000.0]
    runner = JobsRunner(
        client.app.state.session_factory,
        client.app.state.settings,
        client.app.state.email_sender,
        clock=lambda: now[0],
        provider=client.app.state.ai_provider,
    )
    assert runner.run_once()["interviews_expired"] == 0
    h2, iv2 = coding(client, email="grace@example.com")
    expire(client, iv2["id"])
    now[0] += 30
    assert "interviews_expired" not in runner.run_once()  # not yet a minute
    now[0] += 30
    assert runner.run_once() == {"interviews_expired": 1}
    assert stored(client, iv2["id"]).status == InterviewStatus.EXPIRED


# --- what changed after a check ---------------------------------------------------------------------

LINES = CODE.split("\n")


def test_code_changed_after_a_check_says_which_lines_were_added_and_how_many_removed(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    checked(client, h, iv)
    # The two loops replaced by a map lookup: three lines go, four come.
    new = (
        LINES[:3]
        + [
            "        java.util.Map<Integer, Integer> seen = new java.util.HashMap<>();",
            "        for (int i = 0; i < nums.length; i++) {",
            "            if (seen.containsKey(target - nums[i])) return new int[] {seen.get(target - nums[i]), i};",
            "            seen.put(nums[i], i); }",
        ]
        + LINES[6:]
    )
    code = "\n".join(new)
    assert say(client, h, iv, message="Switched to a map.", code=code).status_code == 200
    expire(client, iv["id"])
    assert sweep(client) == 1
    read = get(client, h, iv["id"])["feedback_read"]
    assert {"The conversation so far", "Your code"} <= set(read["confirmed"]["changed"])
    by_label = {c["label"]: c for c in read["confirmed"]["changes"]}
    change = by_label["Your code"]
    assert [new[n - 1] for n in change["added_lines"]] == new[3:7]  # the four new lines, by number
    assert (change["added"], change["removed"]) == (4, 3)
    assert change["text"] == "Your code: 4 lines added, 3 lines removed"
    assert by_label["The conversation so far"]["messages_after"] == 2  # yours, and the interviewer's reply
    assert by_label["The conversation so far"]["text"] == (
        "The conversation so far: 2 messages sent after your check"
    )
    # The sentence before it is as it was: the labels, in order.
    assert read["text"] == (
        "You checked an earlier version before time ran out; it changed after: "
        + ", ".join(read["confirmed"]["changed"])
        + "."
    )


def test_only_line_digests_are_kept_with_the_check_never_a_line(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    checked(client, h, iv)
    kept = stored(client, iv["id"]).plan["feedback_check"]
    flat = repr(kept)
    for line in LINES:
        if len(line.strip()) > 2:
            assert line.strip() not in flat
    code = next(p for p in kept["parts"] if p["label"] == "Your code")
    assert len(code["lines"]) == len(LINES) and all(len(d) == 12 for d in code["lines"])
    export = client.get("/api/v1/me/export", headers=h).json()
    row = next(i for i in export["interviews"] if i["id"] == iv["id"])
    assert "lines" not in repr(row["feedback_check"])  # the export carries labels and the time only


def test_a_check_kept_before_this_says_what_it_said(client):
    h, iv = coding(client)
    say(client, h, iv, code=CODE)
    checked(client, h, iv)
    with client.app.state.session_factory() as db:  # as Volume 16 kept it: digests only
        s = db.scalar(select(PracticeSession).where(PracticeSession.id == iv["id"]))
        check = dict(s.plan["feedback_check"])
        check["v"] = 1
        check.pop("turns")
        check["parts"] = [{"label": p["label"], "digest": p["digest"]} for p in check["parts"]]
        s.plan = {**s.plan, "feedback_check": check}
        db.commit()
    say(client, h, iv, message="And then I'd sort the pairs first.", code=CODE)
    expire(client, iv["id"])
    read = get(client, h, iv["id"])["feedback_read"]
    assert read["confirmed"]["changed"] == ["The conversation so far"]
    assert read["confirmed"]["changes"] == []
    assert read["text"] == (
        "You checked an earlier version before time ran out; it changed after: The conversation so far."
    )
