"""Score eligibility (Durable Saves briefs 07 and 08): which stored scores count in summaries.

Raw stored scores and answered counts are kept; summaries ("best score", averages, "lowest score
first", weekly trends, target coverage, the plan) use only answers long enough to score. An
answer too short to score is answered, with no score (not zero, not its capped number); an answer
whose grading wasn't recorded is unknown. Valid low scores (0, 35) are scores. Synthetic data only.
"""

from __future__ import annotations

import copy
import re

import pytest

from app.careers.eligibility import eligibility, feedback_eligibility
from app.careers.questions import questions_for
from app.models import PracticeAnswer, User
from tests.conftest import auth_headers, register
from tests.test_targets import create, nurse, req

TRACK = "registered-nurse"
LONG = (
    "Last winter on a busy ward I noticed a patient's breathing change during my night round. I checked his "
    "observations again, raised the bed, started oxygen as prescribed and called the doctor using SBAR. Within "
    "the hour his saturation was back to 96%, and I learned to escalate early rather than wait to be certain."
)
SHORT = "I would check the patient and call the doctor."  # under 40 words: too short to score


def test_the_rule():
    assert eligibility("sufficient", 3) == "scored"  # the recorded level wins over the count
    assert eligibility("insufficient", 400) == "too_short"
    # Answers from before the level was recorded: the recorded word count, MIN_WORDS (40) throughout.
    assert eligibility(None, 40) == "scored" and eligibility(None, 39) == "too_short"
    assert eligibility(None, None) == "unknown" and eligibility(None, True) == "unknown"
    assert feedback_eligibility({"word_count": 120, "rating": "Good"}) == "scored"
    assert feedback_eligibility({}) == "unknown" and feedback_eligibility(None) == "unknown"


def _url(qid: str) -> str:
    return f"/api/v1/careers/{TRACK}/questions/{qid}/answers"


def _qid(i: int) -> str:
    return questions_for(TRACK)[i].id


def _insert(c, email: str, qid: str, score: int, feedback_change) -> None:
    """A row as an older version of the app could have stored it (built from a real one)."""
    db = c.app.state.session_factory()
    user = db.query(User).filter(User.email == email).one()
    template = db.query(PracticeAnswer).filter(PracticeAnswer.user_id == user.id).first()
    fb = copy.deepcopy(template.feedback)
    feedback_change(fb)
    db.add(
        PracticeAnswer(
            user_id=user.id,
            track=TRACK,
            question_id=qid,
            difficulty="easy",
            answer="(legacy)",
            score=score,
            feedback=fb,
            provider=template.provider,
            content_version=1,
        )
    )
    db.commit()
    db.close()


@pytest.fixture
def learner(client):
    """Five questions: scored only; too short only; too short (higher raw) beside a lower scored one;
    a legacy short one; a legacy one with nothing recorded."""
    h = auth_headers(register(client, email="ada@example.com"))
    client.post(_url(_qid(0)), headers=h, json={"answer": LONG})
    client.post(_url(_qid(1)), headers=h, json={"answer": SHORT})
    client.post(_url(_qid(2)), headers=h, json={"answer": SHORT})
    _insert(
        client,
        "ada@example.com",
        _qid(2),
        12,
        lambda fb: fb.update(evidence_level="sufficient", word_count=60),
    )
    _insert(
        client,
        "ada@example.com",
        _qid(3),
        30,
        lambda fb: (fb.pop("evidence_level", None), fb.update(word_count=25)),
    )
    _insert(
        client,
        "ada@example.com",
        _qid(4),
        50,
        lambda fb: (fb.pop("evidence_level", None), fb.pop("word_count", None)),
    )
    return h


def _summaries(c, h) -> dict[str, dict]:
    items = c.get(f"/api/v1/careers/{TRACK}/questions", headers=h, params={"page_size": 200}).json()["items"]
    return {q["id"]: q for q in items}


def test_question_summaries_keep_raw_and_add_the_scoreable_best(client, learner):
    s = _summaries(client, learner)
    scored, short, mixed, legacy_short, unknown = (s[_qid(i)] for i in range(5))
    assert scored["score_status"] == "scored" and scored["best_scored"] == scored["best_score"]
    assert (
        short["score_status"] == "too_short"
        and short["best_scored"] is None
        and short["best_score"] is not None
    )
    # The too-short answer's capped stored score is higher than the real one: the real one counts.
    assert mixed["score_status"] == "scored" and mixed["best_scored"] == 12 and mixed["best_score"] > 12
    assert legacy_short["score_status"] == "too_short" and legacy_short["best_scored"] is None
    assert (
        unknown["score_status"] == "unknown"
        and unknown["best_scored"] is None
        and unknown["best_score"] == 50
    )
    untouched = s[_qid(5)]
    assert (
        untouched["score_status"] is None
        and untouched["best_score"] is None
        and untouched["best_scored"] is None
    )


def test_progress_counts_answered_questions_once_and_says_which_have_a_score(client, learner):
    p = client.get(f"/api/v1/careers/{TRACK}/progress", headers=learner).json()
    assert p["answered"] == 5  # unchanged: every answered question
    assert (p["scored"], p["too_short"], p["unknown"]) == (2, 2, 1)


def test_lowest_score_first_ranks_only_scores_and_puts_unscored_answers_after_them(client, learner):
    r = client.get(
        f"/api/v1/me/explore/{TRACK}",
        headers=learner,
        params={"status": "attempted", "sort": "lowest_score", "page_size": 50},
    ).json()
    order = [i["id"] for i in r["items"]]
    status = r["status"]
    scored_part = [q for q in order if status[q]["best_scored"] is not None]
    assert order[: len(scored_part)] == scored_part  # every scored question comes first
    assert [status[q]["best_scored"] for q in scored_part] == sorted(
        status[q]["best_scored"] for q in scored_part
    )
    assert status[_qid(1)]["score_status"] == "too_short" and status[_qid(1)]["best_scored"] is None
    assert status[_qid(4)]["score_status"] == "unknown"


def test_activity_feed_says_too_short_and_filters_and_counts_it_apart(client, learner):
    feed = client.get(
        "/api/v1/me/activity", headers=learner, params={"type": "written_answer", "page_size": 50}
    ).json()["items"]
    short = [i for i in feed if i["status"] == "too_short"]
    assert len(short) == 3 and all(i["status_label"].startswith("Too short to score") for i in short)
    assert any(
        i["status_label"].startswith("Graded 50/100 (how it was graded wasn't recorded)") for i in feed
    )
    only_short = client.get(
        "/api/v1/me/activity", headers=learner, params={"type": "written_answer", "status": "too_short"}
    ).json()
    only_scored = client.get(
        "/api/v1/me/activity", headers=learner, params={"type": "written_answer", "status": "scored"}
    ).json()
    assert only_short["total"] == 3 and only_scored["total"] == 3
    facets = client.get("/api/v1/me/activity/facets", headers=learner).json()
    counts = {f["value"]: f["count"] for f in facets["statuses"]}
    assert counts["too_short"] == 3 and counts["scored"] == 3


def test_analytics_averages_and_trends_use_only_scoreable_answers(client):
    h = auth_headers(register(client))
    client.post(_url(_qid(0)), headers=h, json={"answer": LONG})
    client.post(_url(_qid(1)), headers=h, json={"answer": SHORT})
    a = client.get(f"/api/v1/me/careers/{TRACK}/analytics", headers=h).json()
    long_score = _summaries(client, h)[_qid(0)]["best_scored"]
    week = [p for s in a["trends"] for p in s["points"]]
    assert a["answers"] == 2  # both count as answers
    # The trend's count is its average's denominator: only the scoreable one; the other is counted
    # apart, with why (docs/COMPARING_ATTEMPTS.md).
    assert sum(p["answers"] for p in week) == 1
    assert [p["average_score"] for p in week] == [long_score]
    assert a["not_in_trend"] == [{"rule": "scoring", "reason": "too short to score", "count": 1}]
    for skill in a["skills"]:
        if skill["questions_answered"] and not skill["questions_scored"]:
            assert skill["average_best_score"] is None  # answered, but no score: not zero


def test_a_question_answered_only_too_briefly_has_no_score_anywhere_else_either(client):
    h = nurse(client)
    t = create(client, h)
    triage = req(t, "Perform patient assessment and triage for incoming patients")
    qid = triage["practice"][0]["href"].rsplit("/", 1)[1]
    client.post(f"/api/v1/careers/{TRACK}/questions/{qid}/answers", headers=h, json={"answer": SHORT})
    after = req(client.get(f"/api/v1/targets/{t['id']}", headers=h).json(), triage["text"])
    assert after["coverage"]["level"] == "some"
    assert (
        "none long enough to score" in after["coverage"]["label"] and "/100" not in after["coverage"]["label"]
    )
    retry = [p for p in after["practice"] if p["href"].endswith(qid)]
    assert (
        retry
        and retry[0]["answered"]
        and retry[0]["best_score"] is None
        and "too short to score" in retry[0]["why"]
    )
    # The plan doesn't offer it as a new question, and doesn't quote its capped number.
    plan = client.get("/api/v1/me/plan", headers=h, params={"track": TRACK}).json()
    # The only answer was too short to score, so no "best score is N/100" may appear anywhere.
    assert re.search(r"best score (here )?is \d+/100", repr(plan)) is None


def test_an_answer_with_nothing_recorded_is_listed_as_unknown_not_an_error(client, learner):
    """Release Readiness brief 02/11: such a row made the whole answer list fail (KeyError on
    word_count); now it's listed with evidence_level "unknown", like the summaries say."""
    r = client.get(_url(_qid(4)), headers=learner)
    assert r.status_code == 200
    [row] = r.json()
    assert row["evidence_level"] == "unknown" and row["score"] == 50
    assert row["word_count"] == 1  # "(legacy)": counted from the stored text, a fact, not a decision
    assert _summaries(client, learner)[_qid(4)]["score_status"] == "unknown"
    # the legacy short one (a recorded count under 40) is too short, as the summaries say
    assert [a["evidence_level"] for a in client.get(_url(_qid(3)), headers=learner).json()] == [
        "insufficient"
    ]
