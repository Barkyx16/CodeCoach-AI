"""What the coding interviewer reads (Volume 14, prompt 3; docs/COACH_CONTEXT.md, "The coding
interviewer"): a message and the end-of-interview feedback each preview their material exactly, with
secret-looking strings replaced in messages and code, and a request carrying the preview's fingerprint
is sent only if what would be read is still exactly that.

A recording provider (the real Claude adapter over a fake client) captures every request, so the checks
compare what was previewed with what a provider actually received, byte for byte. Synthetic data only."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select

from app.models import AIInteraction, InterviewTurn, PracticeSession
from app.schemas.interview import RUBRIC_DIMENSIONS, InterviewerReply, InterviewEvaluation, RubricScore
from app.services.ai.anthropic_provider import AnthropicCoach, _numbered
from app.services.rate_limit import SlidingWindowLimiter
from tests.conftest import auth_headers, register
from tests.test_ai_coach import FakeMessages
from tests.test_coach_context import CODE, SECRET, used

# A second synthetic key-shaped string, written in a message rather than in code.
SAID = "ghp_" + "w" * 36
MESSAGE = f"I'd use a hash map. My scratch token was {SAID}, ignore it."


class Recording:
    """The Claude adapter over a fake client: records each interviewer turn and evaluation."""

    name, model = "anthropic", "m"

    def __init__(self):
        self.turn_messages = FakeMessages(
            parsed=InterviewerReply(message="What would you store in the map?", advance_phase=False)
        )
        self.eval_messages = FakeMessages(
            parsed=InterviewEvaluation(
                scores=[
                    RubricScore(dimension=d, score=2, evidence="From the transcript.")
                    for d in RUBRIC_DIMENSIONS
                ],
                overall="developing",
                summary="A start.",
                strengths=["Talked it through."],
                improvements=["Say the complexity."],
                confidence="medium",
            )
        )
        self._turn = AnthropicCoach(
            api_key=None, model="m", client=SimpleNamespace(messages=self.turn_messages)
        )
        self._eval = AnthropicCoach(
            api_key=None, model="m", client=SimpleNamespace(messages=self.eval_messages)
        )
        self.turns: list = []
        self.evaluations: list = []

    def interview_turn(self, ctx):
        self.turns.append(ctx)
        return self._turn.interview_turn(ctx)

    def evaluate_interview(self, ctx):
        self.evaluations.append(ctx)
        return self._eval.evaluate_interview(ctx)

    def __getattr__(self, name):
        raise AssertionError(f"unexpected provider call: {name}")

    @property
    def turn_prompts(self) -> list[str]:
        return [c["messages"][0]["content"] for c in self.turn_messages.calls]

    @property
    def eval_prompts(self) -> list[str]:
        return [c["messages"][0]["content"] for c in self.eval_messages.calls]


def setup(client, email="ada@example.com"):
    h = auth_headers(register(client, email=email))
    rec = Recording()
    client.app.state.ai_provider = rec
    iv = client.post(
        "/api/v1/interviews",
        headers=h,
        json={"kind": "coding", "problem_slug": "two-sum", "duration_minutes": 15},
    )
    assert iv.status_code == 201, iv.text
    return h, rec, iv.json()


def preview(client, h, iv, message=MESSAGE, code=CODE, **extra):
    body = {"message": message, "code": code, **extra}
    return client.post(f"/api/v1/interviews/{iv['id']}/message/preview", headers=h, json=body)


def say(client, h, iv, approved=None, message=MESSAGE, code=CODE, **extra):
    body = {"message": message, "code": code, **extra}
    if approved is not None:
        body["approved_context"] = approved
    return client.post(f"/api/v1/interviews/{iv['id']}/messages", headers=h, json=body)


def feedback_preview(client, h, iv, ending="finished", code=CODE):
    body = {"ending": ending} if code is None else {"ending": ending, "code": code}
    return client.post(f"/api/v1/interviews/{iv['id']}/feedback/preview", headers=h, json=body)


def sent(item) -> str:
    """An item's text as it appears in the prompt: code is sent with line numbers added (and said)."""
    return _numbered(item["text"]) if item["key"] == "code" else item["text"]


def turns(client, iv) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(InterviewTurn).where(InterviewTurn.session_id == iv["id"])
        )


def test_the_message_preview_is_exactly_what_the_interviewer_reads(client):
    h, rec, iv = setup(client)
    before = used(client, h)
    p = preview(client, h, iv)
    assert p.status_code == 200, p.text
    p = p.json()
    assert p["operation"] == "interview_message"
    items = {i["key"]: i for i in p["items"]}
    assert list(items) == ["message", "conversation", "code", "checks", "phase"]
    # Secret-looking strings replaced in the message and in the code, and said.
    assert SAID not in items["message"]["text"] and "[REDACTED]" in items["message"]["text"]
    assert items["message"]["notes"] == ["1 secret-looking string replaced with [REDACTED]."]
    assert SECRET not in items["code"]["text"] and items["code"]["notes"] == [
        "1 secret-looking string replaced with [REDACTED]."
    ]
    assert items["conversation"]["text"].startswith("[clarify] INTERVIEWER: ")
    assert items["phase"]["derived"] and items["phase"]["text"].startswith("Current phase: clarify (")
    assert p["recipient_kind"] == "external" and "built-in interviewer" in p["fallback"]
    assert p["required_public"][0].startswith("The problem “Two Sum”")
    # Checking spent nothing and called nothing.
    assert used(client, h) == before and len(rec.turns) == 1  # the opening only

    r = say(client, h, iv, p["context_fingerprint"])
    assert r.status_code == 200, r.text
    assert used(client, h) == before + 1
    prompt = rec.turn_prompts[-1]
    for item in items.values():
        assert sent(item) in prompt, item["key"]
    assert SAID not in prompt and SECRET not in prompt
    # The stored transcript keeps what was written: it's the learner's own record.
    assert r.json()["turns"][1]["content"] == MESSAGE


def test_changed_code_is_refused_with_the_new_preview_and_nothing_is_stored_or_spent(client):
    h, rec, iv = setup(client)
    p = preview(client, h, iv).json()
    before, stored = used(client, h), turns(client, iv)
    changed = CODE.replace("return new int[0];", "return null;")
    r = say(client, h, iv, p["context_fingerprint"], code=changed)
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    fresh = {i["key"]: i["text"] for i in r.json()["error"]["details"]["preview"]["items"]}
    assert "return null;" in fresh["code"]
    assert used(client, h) == before and turns(client, iv) == stored and len(rec.turns) == 1
    # Other words under the same approval are refused the same way.
    assert say(client, h, iv, p["context_fingerprint"], message="Something else.").status_code == 409
    # Sent against its own preview, it goes.
    again = r.json()["error"]["details"]["preview"]["context_fingerprint"]
    assert say(client, h, iv, again, code=changed).status_code == 200


def test_a_conversation_that_moved_on_is_refused(client):
    h, rec, iv = setup(client)
    p = preview(client, h, iv, message="First.").json()
    assert (
        say(client, h, iv, message="Sent from another tab.").status_code == 200
    )  # unbound, as an older page
    r = say(client, h, iv, p["context_fingerprint"], message="First.")
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    convo = next(i for i in r.json()["error"]["details"]["preview"]["items"] if i["key"] == "conversation")
    assert "CANDIDATE: Sent from another tab." in convo["text"]
    # A preview written against an older transcript is refused as the message would be.
    stale = preview(client, h, iv, after_seq=1)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "interview_advanced"


def test_secrets_in_earlier_messages_are_replaced_every_time_they_are_read(client):
    h, rec, iv = setup(client)
    assert say(client, h, iv, code="").status_code == 200  # unbound: still replaced
    assert SAID not in rec.turn_prompts[-1]
    p = preview(client, h, iv, message="Next.", code="").json()
    convo = next(i for i in p["items"] if i["key"] == "conversation")
    assert SAID not in convo["text"] and convo["notes"] == [
        "1 secret-looking string replaced with [REDACTED]."
    ]
    code = next(i for i in p["items"] if i["key"] == "code")
    assert "Your editor is empty: the interviewer is told so." in code["notes"]
    # The feedback reads the same conversation, replaced the same way.
    f = feedback_preview(client, h, iv).json()
    assert (
        client.post(
            f"/api/v1/interviews/{iv['id']}/finish",
            headers=h,
            json={"code": CODE, "approved_context": f["context_fingerprint"]},
        ).status_code
        == 200
    )
    assert SAID not in rec.eval_prompts[-1] and SECRET not in rec.eval_prompts[-1]


def test_a_resumed_interview_previews_from_the_servers_state(client):
    h, rec, iv = setup(client)
    assert say(client, h, iv, message="Here's my code.", code=CODE).status_code == 200
    # Another device, nothing in its editor yet: the code is the one last sent.
    p = preview(client, h, iv, message="Back again.", code=None).json()
    code = next(i for i in p["items"] if i["key"] == "code")
    assert code["source"].startswith("As last sent with a message: ") and "twoSum" in code["text"]
    assert "Here's my code." in next(i for i in p["items"] if i["key"] == "conversation")["text"]
    assert say(client, h, iv, p["context_fingerprint"], message="Back again.", code=None).status_code == 200


def test_another_accounts_interview_is_not_found(client):
    h, rec, iv = setup(client)
    other = auth_headers(register(client, email="other@example.com"))
    p = preview(client, h, iv).json()
    assert preview(client, other, iv).status_code == 404
    assert feedback_preview(client, other, iv).status_code == 404
    assert say(client, other, iv, p["context_fingerprint"]).status_code == 404
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/finish",
        headers=other,
        json={"approved_context": p["context_fingerprint"]},
    )
    assert r.status_code == 404
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["status"] == "in_progress"


def test_a_replayed_bound_message_is_answered_once(client):
    h, rec, iv = setup(client)
    p = preview(client, h, iv).json()
    before = used(client, h)
    first = say(client, h, iv, p["context_fingerprint"], client_request_id="replay-key-0001")
    again = say(client, h, iv, p["context_fingerprint"], client_request_id="replay-key-0001")
    assert first.status_code == again.status_code == 200
    assert first.json()["turns"] == again.json()["turns"]
    assert used(client, h) == before + 1 and len(rec.turns) == 2  # the opening and one reply
    # The same key with other words is refused, never taken as sent.
    other = say(
        client, h, iv, p["context_fingerprint"], message="Other words.", client_request_id="replay-key-0001"
    )
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"


def test_the_feedback_is_previewed_and_bound_the_same_way(client):
    h, rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    f = feedback_preview(client, h, iv).json()
    assert f["operation"] == "interview_feedback"
    items = {i["key"]: i for i in f["items"]}
    assert list(items) == ["conversation", "code", "checks", "ending"]
    assert items["ending"]["text"] == "How it ended: finished."
    before = used(client, h)
    changed = CODE + "\n// one more line"
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/finish",
        headers=h,
        json={"code": changed, "approved_context": f["context_fingerprint"]},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    assert client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()["status"] == "in_progress"
    assert used(client, h) == before and rec.evaluations == []
    r = client.post(
        f"/api/v1/interviews/{iv['id']}/finish",
        headers=h,
        json={"code": CODE, "approved_context": f["context_fingerprint"]},
    )
    assert r.status_code == 200 and r.json()["status"] == "completed"
    prompt = rec.eval_prompts[-1]
    for item in items.values():
        assert sent(item) in prompt, item["key"]


def test_ending_early_previews_the_code_last_sent(client):
    h, rec, iv = setup(client)
    assert say(client, h, iv, code=CODE).status_code == 200
    f = feedback_preview(client, h, iv, ending="abandoned", code=None).json()
    items = {i["key"]: i for i in f["items"]}
    assert items["ending"]["text"] == "How it ended: abandoned."
    assert items["code"]["source"].startswith("As last sent with a message")
    wrong = feedback_preview(client, h, iv, ending="finished").json()["context_fingerprint"]
    bad = client.post(f"/api/v1/interviews/{iv['id']}/abandon", headers=h, json={"approved_context": wrong})
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "context_changed"
    ok = client.post(
        f"/api/v1/interviews/{iv['id']}/abandon",
        headers=h,
        json={"approved_context": f["context_fingerprint"]},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "abandoned"
    assert items["conversation"]["text"] in rec.eval_prompts[-1]


def test_previews_call_nothing_spend_nothing_store_nothing_and_are_rate_limited(client):
    h, rec, iv = setup(client)
    before, stored = used(client, h), turns(client, iv)
    for _ in range(10):
        assert preview(client, h, iv).status_code == 200
        assert feedback_preview(client, h, iv).status_code == 200
    assert used(client, h) == before and turns(client, iv) == stored
    assert len(rec.turns) == 1 and rec.evaluations == []
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIInteraction)) == 1  # the opening
    client.app.state.coach_preview_limiter = SlidingWindowLimiter(2, 60)
    assert [preview(client, h, iv).status_code for _ in range(3)] == [200, 200, 429]


def test_a_preview_past_the_deadline_neither_evaluates_nor_sends(client):
    h, rec, iv = setup(client)
    with client.app.state.session_factory() as db:
        s = db.get(PracticeSession, iv["id"])
        s.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    r = preview(client, h, iv)
    assert r.status_code == 409 and r.json()["error"]["details"]["status"] == "expired"
    assert rec.evaluations == []


def test_the_built_in_interviewer_is_labelled_as_such(client):
    h = auth_headers(register(client))
    iv = client.post(
        "/api/v1/interviews", headers=h, json={"kind": "coding", "problem_slug": "two-sum"}
    ).json()
    p = preview(client, h, iv).json()
    assert p["recipient"] == "The built-in interviewer, on CodeCoach's own server: nothing leaves it"
    assert p["recipient_kind"] == "built_in" and p["fallback"] is None
    # Sent without a preview (an older page, or the API used directly), it works as before.
    assert say(client, h, iv).status_code == 200
