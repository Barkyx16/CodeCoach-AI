"""A hint panel inside the coding interview (Volume 17, prompt 4; docs/ATTEMPT_CONDITIONS.md,
docs/COACH_CONTEXT.md): `POST /interviews/{id}/hint` asks for the problem's own hint ladder through
the coach, exactly as the workspace does (the same ladder, the same budget), with the code last sent,
and the interview records it: its level, when it was shown and after how many messages. Asking for a
level already asked for in this interview gives that hint again with no second request. The
interview's conditions say each was during the interview; the feedback reads that hints were used, in
the same words its preview shows; the interview lists them. Refused once the interview is over or its
time is up, for a career interview, and for another account. Synthetic data only."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import AIAction, AIInteraction
from app.services.ai.offline import OfflineCoach
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import Recording, feedback_preview, say
from tests.test_feedback_read import expire, finish, get
from tests.test_question_rounds import start as start_round


class WithHints(Recording):
    """The recorder of what the interviewer reads, with hints from the built-in coach."""

    def hint(self, ctx):
        return OfflineCoach().hint(ctx)


def setup(client, email="ada@example.com"):
    h = auth_headers(register(client, email=email))
    rec = WithHints()
    client.app.state.ai_provider = rec
    r = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "coding", "problem_slug": "two-sum", "duration_minutes": 15},
    )
    assert r.status_code == 201, r.text
    return h, rec, r.json()


def hint(client, h, iv, level, **extra):
    return client.post(f"/api/v1/interviews/{iv['id']}/hint", headers=h, json={"level": level, **extra})


def hints_shown(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(AIInteraction).where(AIInteraction.action == AIAction.HINT)
        )


def test_a_hint_in_the_interview_is_shown_and_recorded_with_its_level_and_turn(client):
    h, _rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200  # a message and the interviewer's reply
    r = hint(client, h, iv, 1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hint"]["level"] == 1 and body["hint"]["content"] and body["repeated"] is False
    assert body["record"]["level"] == 1 and body["record"]["turn"] == len(get(client, h, iv["id"])["turns"])
    assert body["record"]["level_name"] == body["hint"]["level_name"]
    listed = get(client, h, iv["id"])["hints"]
    assert [x["level"] for x in listed] == [1] and listed[0]["at"] == body["record"]["at"]


def test_asking_for_the_same_level_again_gives_that_hint_with_no_second_request(client):
    h, _rec, iv = setup(client)
    first = hint(client, h, iv, 1).json()
    n = hints_shown(client)
    again = hint(client, h, iv, 1)
    assert again.status_code == 200 and again.json()["repeated"] is True
    assert again.json()["hint"]["content"] == first["hint"]["content"]
    assert hints_shown(client) == n  # nothing asked of the coach again
    assert [x["level"] for x in get(client, h, iv["id"])["hints"]] == [1]  # recorded once
    second = hint(client, h, iv, 2)
    assert second.status_code == 200 and [x["level"] for x in get(client, h, iv["id"])["hints"]] == [1, 2]


def test_the_ladder_still_unlocks_one_level_at_a_time(client):
    h, _rec, iv = setup(client)
    r = hint(client, h, iv, 2)
    assert r.status_code == 409 and r.json()["error"]["code"] == "hint_locked"
    assert get(client, h, iv["id"])["hints"] == []


def test_the_feedback_reads_that_hints_were_used_in_the_words_its_preview_shows(client):
    h, rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    hint(client, h, iv, 1)
    preview = feedback_preview(client, h, iv).json()
    ending = next(i for i in preview["items"] if i["key"] == "ending")
    line = "Hints the candidate asked for during it: level 1 (nudge)."
    assert line in ending["text"]
    assert finish(client, h, iv["id"], approved_context=preview["context_fingerprint"]).status_code == 200
    [ctx] = rec.evaluations
    assert ctx.hints_during == ("level 1 (nudge)",)
    assert line in rec.eval_prompts[0]  # what was sent says it, word for word


def test_without_hints_the_feedback_reads_as_before(client):
    h, rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    preview = feedback_preview(client, h, iv).json()
    ending = next(i for i in preview["items"] if i["key"] == "ending")
    assert ending["text"] == "How it ended: finished."


def test_the_interviews_conditions_say_the_hint_came_during_it(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    hint(client, h, iv, 1)
    expire(client, iv["id"])
    got = get(client, h, iv["id"])
    [shown] = got["conditions"]["help"]
    assert shown["label"] == "Hint shown" and shown["detail"].endswith("during the interview")
    assert got["hints"][0]["level"] == 1


def test_refused_once_the_interview_is_over_or_its_time_is_up(client):
    h, _rec, iv = setup(client)
    expire(client, iv["id"])
    r = hint(client, h, iv, 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "interview_closed"
    h2, _rec, iv2 = setup(client, email="grace@example.com")
    client.post(f"/api/v1/interviews/{iv2['id']}/abandon", headers=h2, json={})
    r = hint(client, h2, iv2, 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "interview_closed"
    assert hints_shown(client) == 0


def test_a_career_interview_has_no_hint_panel_and_another_account_cant_ask(client):
    nurse = auth_headers(register(client, email="nurse@example.com", career_track="registered-nurse"))
    round_ = start_round(client, nurse).json()
    r = client.post(f"/api/v1/interviews/{round_['id']}/hint", headers=nurse, json={"level": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "wrong_interview_kind"
    h, _rec, iv = setup(client)
    other = auth_headers(register(client, email="other@example.com"))
    assert hint(client, other, iv, 1).status_code == 404
    assert hints_shown(client) == 0


def test_a_hint_bound_to_a_preview_is_sent_only_while_that_is_still_what_the_coach_reads(client):
    h, _rec, iv = setup(client)
    say(client, h, iv, code=CODE)
    pv = client.post(
        "/api/v1/ai/hint/preview",
        headers=h,
        json={"problem_slug": "two-sum", "source_code": CODE, "level": 1},
    )
    assert pv.status_code == 200, pv.text
    fp = pv.json()["context_fingerprint"]
    say(
        client, h, iv, message="Then I'd use a map.", code=CODE + "\n// changed"
    )  # the code last sent moved on
    stale = hint(client, h, iv, 1, approved_context=fp)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "context_changed"
    assert get(client, h, iv["id"])["hints"] == [] and hints_shown(client) == 0
    fresh = stale.json()["error"]["details"]["preview"]["context_fingerprint"]
    ok = hint(client, h, iv, 1, approved_context=fresh)
    assert ok.status_code == 200 and [x["level"] for x in get(client, h, iv["id"])["hints"]] == [1]
