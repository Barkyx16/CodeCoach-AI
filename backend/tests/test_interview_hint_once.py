"""One request to the coach per interview and level (Volume 18, prompt 2; docs/COACH_CONTEXT.md, "Hints
inside the interview"). An interview's hint at a level has one request key, the interview's and the
level's, whatever key the page sent, and the coach looks again for that key once it holds the AI turn.
So two tabs asking for the same new level are one request: the second gets the first's hint, or waits
its turn and then gets it, and the provider is asked once; the interview records it once. On
PostgreSQL, the wait is shown with two real transactions. Synthetic data only."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from app.models import AIAction, AIInteraction, PracticeSession, Problem
from app.services.ai import service as ai_service
from app.services.ai.offline import OfflineCoach
from app.services.interviews import interview_hint_key
from tests.conftest import auth_headers, register
from tests.test_coach_context import CODE
from tests.test_coach_context_interviewer import say
from tests.test_interview_hints import WithHints, hint, setup
from tests.test_request_identity import review


class Counting(WithHints):
    """The built-in coach's hints, counted: how many times the provider was asked."""

    def __init__(self):
        super().__init__()
        self.asked = 0

    def hint(self, ctx):
        self.asked += 1
        return super().hint(ctx)


def counted(client, email="ada@example.com"):
    h, _rec, iv = setup(client, email)
    rec = Counting()
    client.app.state.ai_provider = rec
    assert say(client, h, iv, code=CODE).status_code == 200
    return h, rec, iv


def interactions(client, key=None) -> int:
    with client.app.state.session_factory() as db:
        q = select(func.count()).select_from(AIInteraction).where(AIInteraction.action == AIAction.HINT)
        if key is not None:
            q = q.where(AIInteraction.client_request_id == key)
        return db.scalar(q)


def recorded(client, iv) -> list[dict]:
    with client.app.state.session_factory() as db:
        return list((db.get(PracticeSession, iv["id"]).plan or {}).get("hints") or [])


def workspace_hint(client, h, key="ws-key-0001"):
    r = client.post(
        "/api/v1/ai/hint",
        headers=h,
        json={"problem_slug": "two-sum", "source_code": CODE, "level": 1, "client_request_id": key},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_two_tabs_with_their_own_keys_are_one_request(client):
    h, rec, iv = counted(client)
    first = hint(client, h, iv, 1, client_request_id="tab-a-0001")
    second = hint(client, h, iv, 1, client_request_id="tab-b-0001")
    assert first.status_code == second.status_code == 200
    assert second.json()["hint"]["content"] == first.json()["hint"]["content"]
    assert rec.asked == 1 and interactions(client) == 1
    assert [x["level"] for x in recorded(client, iv)] == [1]


def test_answered_for_one_tab_before_the_interview_recorded_it_the_other_gets_that_hint(client):
    """The first tab's request reached the coach and was answered; the second asked before the
    interview recorded it (its `again` check found nothing). The second is the same request."""
    h, rec, iv = counted(client)
    first = hint(client, h, iv, 1, client_request_id="tab-a-0001").json()
    with client.app.state.session_factory() as db:  # as if the interview hadn't recorded it yet
        s = db.get(PracticeSession, iv["id"])
        s.plan = {k: v for k, v in (s.plan or {}).items() if k != "hints"}
        db.commit()
    second = hint(client, h, iv, 1, client_request_id="tab-b-0001")
    assert second.status_code == 200, second.text
    assert second.json()["hint"]["content"] == first["hint"]["content"]
    assert rec.asked == 1 and interactions(client, interview_hint_key(iv["id"], 1)) == 1
    [kept] = recorded(client, iv)
    with client.app.state.session_factory() as db:
        row = db.scalar(
            select(AIInteraction.id).where(AIInteraction.client_request_id == interview_hint_key(iv["id"], 1))
        )
    assert kept["interaction_id"] == row


def test_the_coach_looks_again_once_it_holds_the_turn(client, monkeypatch):
    """A copy of the request answered while this one waited for the AI turn: found after the wait,
    so the provider isn't asked."""
    h, rec, iv = counted(client)
    workspace_hint(client, h)  # a hint's content to answer with (the provider asked once)
    key = interview_hint_key(iv["id"], 1)
    real = ai_service.CoachService.check_budget

    def answered_meanwhile(self, user):
        real(self, user)
        src = self.db.scalar(select(AIInteraction).where(AIInteraction.client_request_id == "ws-key-0001"))
        self.db.add(
            AIInteraction(
                user_id=user.id,
                problem_id=src.problem_id,
                action=AIAction.HINT,
                hint_level=1,
                client_request_id=key,
                provider=src.provider,
                model=src.model,
                response=src.response,
            )
        )
        self.db.flush()

    monkeypatch.setattr(ai_service.CoachService, "check_budget", answered_meanwhile)
    r = hint(client, h, iv, 1)
    assert r.status_code == 200, r.text
    assert rec.asked == 1  # the workspace's only
    assert interactions(client, key) == 1


def test_a_hint_asked_from_other_code_meanwhile_is_still_the_interviews_one_hint(client):
    """The same key with other material (code sent between the two tabs' checks): the second tab
    gets the hint the interview has for the level, not a refusal, and nothing is asked twice."""
    h, rec, iv = counted(client)
    first = hint(client, h, iv, 1).json()
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.plan = {k: v for k, v in (s.plan or {}).items() if k != "hints"}
        s.final_code = CODE + "\n// more"
        db.commit()
    second = hint(client, h, iv, 1)
    assert second.status_code == 200, second.text
    assert second.json()["hint"]["content"] == first["hint"]["content"]
    assert rec.asked == 1


def test_another_interview_or_level_is_its_own_request(client):
    h, rec, iv = counted(client)
    hint(client, h, iv, 1)
    assert hint(client, h, iv, 2).status_code == 200
    assert rec.asked == 2
    assert interview_hint_key(iv["id"], 1) != interview_hint_key(iv["id"], 2)


def test_on_postgresql_a_tab_waiting_for_the_turn_then_gets_the_first_tabs_hint(client):
    """Two real transactions: the first tab's request holds the user's AI turn (the advisory lock,
    taken in another connection) while the second asks: it's refused to wait, and nothing is asked.
    The first's answer is committed with the interview's key and the turn released; asked again, the
    second gets that answer and the provider is never asked."""
    with client.app.state.session_factory() as probe:
        if probe.get_bind().dialect.name != "postgresql":
            pytest.skip("needs PostgreSQL: SQLite has no AI turn to hold")
    h, rec, iv = counted(client)
    workspace_hint(client, h)
    asked_before = rec.asked
    key = interview_hint_key(iv["id"], 1)
    with client.app.state.session_factory() as first:
        user_id = first.get(PracticeSession, iv["id"]).user_id
        assert first.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": ai_service._turn_key(user_id)},
        )
        waiting = hint(client, h, iv, 1)
        assert waiting.status_code == 429 and waiting.json()["error"]["code"] == "ai_request_in_progress"
        assert rec.asked == asked_before
        src = first.scalar(select(AIInteraction).where(AIInteraction.client_request_id == "ws-key-0001"))
        problem = first.scalar(select(Problem.id).where(Problem.slug == "two-sum"))
        first.add(
            AIInteraction(
                user_id=user_id,
                problem_id=problem,
                action=AIAction.HINT,
                hint_level=1,
                client_request_id=key,
                provider=src.provider,
                model=src.model,
                response=src.response,
            )
        )
        first.commit()  # the first tab's answer, and the turn released
    again = hint(client, h, iv, 1)
    assert again.status_code == 200, again.text
    assert rec.asked == asked_before and interactions(client, key) == 1
    assert [x["level"] for x in recorded(client, iv)] == [1]


@pytest.fixture
def reviews_asked(monkeypatch) -> dict[str, int]:
    """How many times the built-in coach was asked for a review."""
    asked = {"review": 0}
    original = OfflineCoach.review

    def counting(self, ctx):
        asked["review"] += 1
        return original(self, ctx)

    monkeypatch.setattr(OfflineCoach, "review", counting)
    return asked


def test_a_keyed_code_review_looks_again_once_it_holds_the_turn(client, monkeypatch, reviews_asked):
    """The same look after the wait, for a keyed code review: a copy answered meanwhile is that
    review, and the provider isn't asked again."""
    h = auth_headers(register(client, email="rev@example.com"))
    first = review(client, h, key="review-key-02")
    assert first.status_code == 200 and reviews_asked["review"] == 1
    real = ai_service.CoachService.check_budget

    def answered_meanwhile(self, user):
        real(self, user)
        src = self.db.scalar(select(AIInteraction).where(AIInteraction.client_request_id == "review-key-02"))
        self.db.add(
            AIInteraction(
                user_id=user.id,
                problem_id=src.problem_id,
                action=AIAction.REVIEW,
                client_request_id="review-key-03",
                provider=src.provider,
                model=src.model,
                response=src.response,
            )
        )
        self.db.flush()

    monkeypatch.setattr(ai_service.CoachService, "check_budget", answered_meanwhile)
    second = review(client, h, key="review-key-03")
    assert second.status_code == 200, second.text
    assert second.json()["review"] == first.json()["review"] and reviews_asked["review"] == 1
