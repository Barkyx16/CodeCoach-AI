"""Server-side ownership of saved answers, interviews and coaching records: account B can't read,
change or attach account A's records by changing identifiers or request bodies, and nothing
private comes back in the refusal. Ownership comes from the signed-in account, never from the
request. Complements the per-feature privacy tests (answer review, interviews, rounds,
submissions, scenarios, drills, shares)."""

from sqlalchemy import select

from app.careers.questions import questions_for
from app.models import AnswerFlag, PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
Q = next(q for q in questions_for(TRACK) if q.kind == "behavioral")
SECRET = "ADA-PRIVATE-7731"
ANSWER = (
    f"Last winter on a night shift I was responsible for five patients ({SECRET}). One patient's oxygen dropped "
    "during my assessment, so I checked his observations again, started oxygen per protocol and called the rapid "
    "response team. He was stable within 30 minutes, and I learned to escalate early."
)


def nurse(client, email):
    return auth_headers(register(client, email=email, career_track=TRACK))


def post_answer(client, h, text=ANSWER, **extra):
    r = client.post(
        f"/api/v1/careers/{TRACK}/questions/{Q.id}/answers", headers=h, json={"answer": text, **extra}
    )
    assert r.status_code == 201, r.text
    return r.json()


def refused(r, codes=(404,)):
    """A refusal that tells the other account nothing about the record."""
    return r.status_code in codes and SECRET not in r.text


def test_a_questions_answers_are_listed_only_for_the_account_that_wrote_them(client):
    ada, bea = nurse(client, "ada@example.com"), nurse(client, "bea@example.com")
    post_answer(client, ada)
    url = f"/api/v1/careers/{TRACK}/questions/{Q.id}/answers"
    mine = client.get(url, headers=bea)
    assert mine.status_code == 200 and mine.json() == [] and SECRET not in mine.text
    assert client.get(url).status_code == 401  # not signed in: nothing listed


def test_the_answer_belongs_to_whoever_is_signed_in_whatever_the_body_says(client):
    ada_token = register(client, email="ada@example.com", career_track=TRACK)
    ada, bea = auth_headers(ada_token), nurse(client, "bea@example.com")
    out = post_answer(client, bea, text=ANSWER.replace(SECRET, "BEA"), user_id=ada_token["user"]["id"])
    with client.app.state.session_factory() as db:
        row = db.get(PracticeAnswer, out["id"])
        assert row is not None and row.user_id != ada_token["user"]["id"]
    assert client.get(f"/api/v1/careers/{TRACK}/questions/{Q.id}/answers", headers=ada).json() == []


def test_another_account_cannot_remove_a_flag_or_share_an_answer(client):
    ada, bea = nurse(client, "ada@example.com"), nurse(client, "bea@example.com")
    a = post_answer(client, ada)
    flags = client.post(
        f"/api/v1/me/answers/{a['id']}/flags",
        headers=ada,
        json={"criterion": "Overall", "kind": "unclear", "note": "n"},
    ).json()["flags"]
    flag_id = flags[0]["id"]
    assert refused(client.delete(f"/api/v1/me/answers/{a['id']}/flags/{flag_id}", headers=bea))
    with client.app.state.session_factory() as db:
        assert db.scalar(select(AnswerFlag).where(AnswerFlag.id == flag_id)) is not None  # still there
    # Sharing someone else's answer by its id.
    share = client.post(
        "/api/v1/me/shares", headers=bea, json={"answer_id": a["id"], "acknowledge_link_access": True}
    )
    assert refused(share)


def test_another_account_cannot_read_or_drive_a_question_interview(client):
    ada, bea = nurse(client, "ada@example.com"), nurse(client, "bea@example.com")
    iv = client.post("/api/v1/interviews", headers=ada, json={"kind": "questions"})
    assert iv.status_code == 201, iv.text
    iv_id = iv.json()["id"]
    first = client.post(
        f"/api/v1/interviews/{iv_id}/answers",
        headers=ada,
        json={"question_index": 0, "answer": ANSWER, "source": "typed"},
    )
    assert first.status_code == 200, first.text
    base = f"/api/v1/interviews/{iv_id}"
    attempts = {
        "read": client.get(base, headers=bea),
        "answer": client.post(
            f"{base}/answers",
            headers=bea,
            json={"question_index": 1, "answer": "Bea's words", "source": "typed"},
        ),
        "follow-up": client.post(f"{base}/followup", headers=bea, json={"answer": "x", "source": "typed"}),
        "skip follow-up": client.post(f"{base}/followup/skip", headers=bea),
        "skip": client.post(f"{base}/skip", headers=bea, json={"question_index": 1}),
        "abandon": client.post(f"{base}/abandon", headers=bea),
        "finish": client.post(f"{base}/finish", headers=bea),
        "review": client.get(f"{base}/review", headers=bea),
        "comparison": client.get(f"{base}/questions/0/comparison", headers=bea),
        "retry": client.post(
            f"{base}/questions/0/retries", headers=bea, json={"answer": "x", "source": "typed"}
        ),
    }
    # 404 for every action (not a validation error, which would be checked before ownership).
    assert {k: r.status_code for k, r in attempts.items() if not refused(r)} == {}
    # Ada's interview is exactly as she left it.
    after = client.get(base, headers=ada).json()
    assert after["status"] == iv.json()["status"] and SECRET in str(after)
    assert client.get("/api/v1/interviews", headers=bea).json()["total"] == 0


def test_another_account_cannot_open_an_ai_history_item(client):
    ada, bea = nurse(client, "ada@example.com"), nurse(client, "bea@example.com")
    r = client.post(
        "/api/v1/ai/hint", headers=ada, json={"problem_slug": "two-sum", "code": f"// {SECRET}", "level": 1}
    )
    assert r.status_code == 200, r.text
    item = client.get("/api/v1/me/ai-history", headers=ada).json()["items"][0]
    assert refused(client.get(f"/api/v1/me/ai-history/{item['id']}", headers=bea))
    assert client.get(f"/api/v1/me/ai-history/{item['id']}").status_code == 401
