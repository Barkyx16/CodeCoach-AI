"""One comparison contract for replay and charts (Volume 12, prompt 6; docs/COMPARING_ATTEMPTS.md).
The rules themselves, then the same persisted answers followed through the question page, the
progress chart and an interview retry: identical classifications and explanations everywhere,
cohorts and denominators that match. Synthetic data only."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.careers.comparability import CONTRACT_VERSION, HELP_NONE, AttemptFacts, classify, score_basis
from app.models import PracticeAnswer
from tests.conftest import auth_headers, register

TRACK = "registered-nurse"
LONG = (
    "Last winter I noticed a patient's oxygen dropping during my 2 a.m. patient assessment. I checked his vital "
    "signs, started oxygen per protocol and called the rapid response team. I updated the doctor and documented "
    "everything. He was stable within 30 minutes and I learned to escalate early."
)
LONGER = LONG + " Since then I teach new nurses to trust the early signs and to call for help sooner."
SHORT = "I called for help and it went fine."


def facts(**over) -> AttemptFacts:
    base = dict(
        id="a",
        track=TRACK,
        question_id="q",
        question_version=1,
        scale="0-100",
        rubric="v10",
        source="rules",
        scoring="scored",
        format="single",
        help=(HELP_NONE,),
    )
    return AttemptFacts(**{**base, **over})


# --- the rules ------------------------------------------------------------------------------------


def test_the_same_everything_is_comparable():
    c = classify(facts(id="a"), facts(id="b"))
    assert (c.outcome, c.scores_comparable, c.points_comparable) == ("comparable", True, True)
    assert c.explanation.endswith(f"(Comparison rules v{CONTRACT_VERSION})")


def test_a_rubric_change_is_partly_comparable_and_the_numbers_dont_compare():
    c = classify(facts(rubric="v9"), facts(rubric="v10"))
    assert (c.outcome, c.scores_comparable, c.points_comparable) == ("partially_comparable", False, True)
    assert (
        "scored under different rubrics (v9 and v10): compare what you wrote, not the numbers"
        in c.explanation
    )


def test_a_question_change_and_a_too_short_answer_are_partly_comparable_without_scores():
    c = classify(facts(question_version=1), facts(question_version=2))
    assert c.outcome == "partially_comparable" and not c.scores_comparable
    assert "the question was changed in between (version 1, now 2)" in c.explanation
    c = classify(facts(scoring="too_short"), facts())
    assert (
        c.outcome == "partially_comparable"
        and not c.scores_comparable
        and "one was too short to score" in c.explanation
    )


def test_different_conditions_keep_the_scores_comparable_and_are_named():
    c = classify(facts(format="interview"), facts(format="retry"))
    assert (c.outcome, c.scores_comparable) == ("partially_comparable", True)
    assert (
        "answered in a timed mock interview, the later one as a retry after a mock interview" in c.explanation
    )
    c = classify(facts(help=(HELP_NONE,)), facts(help=("Hint shown",)))
    assert (c.outcome, c.scores_comparable, c.rules) == ("partially_comparable", True, ("help",))
    assert "before the earlier one, none recorded; before the later one, hint shown" in c.explanation


def test_missing_metadata_is_unknown_and_names_the_field():
    c = classify(facts(rubric=None), facts())
    assert (c.outcome, c.scores_comparable, c.points_comparable) == ("unknown", False, False)
    assert "which rubric graded one of them wasn't recorded" in c.explanation
    c = classify(facts(help=None, help_recorded_from=datetime(2026, 11, 14).date()), facts())
    assert (
        c.outcome == "unknown"
        and "in-app help before one of them wasn't recorded (it's recorded from 14 Nov 2026)" in c.explanation
    )
    assert classify(facts(source=None), facts()).rules == ("source",)
    assert classify(facts(scoring="unknown"), facts()).rules == ("scoring",)


def test_different_questions_scales_or_evaluators_are_incompatible_and_never_converted():
    c = classify(facts(question_id="q1"), facts(question_id="q2"))
    assert c.outcome == "incompatible" and c.rules == ("question",)
    c = classify(facts(scale="0-4"), facts(scale="0-100"))
    assert c.outcome == "incompatible" and "each keeps its own score, never converted" in c.explanation
    c = classify(facts(source="person"), facts(source="rules"))
    assert c.outcome == "incompatible" and "(a person and fixed rules)" in c.explanation
    # Something known to be incompatible isn't hidden behind something missing.
    assert classify(facts(scale="0-4", rubric=None), facts()).outcome == "incompatible"


def test_a_trend_series_needs_a_known_score_basis():
    assert score_basis(facts())[0] == "Graded by fixed rules, rubric v10, scored 0-100"
    assert score_basis(facts(scoring="too_short"))[1].text == "too short to score"
    assert score_basis(facts(rubric=None))[1].text == "which rubric graded it wasn't recorded"
    assert score_basis(facts(source=None))[1].rule == "source"


# --- the same answers through every surface ---------------------------------------------------------


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=TRACK))


def answer(client, h, qid, text, **body):
    r = client.post(
        f"/api/v1/careers/{TRACK}/questions/{qid}/answers", headers=h, json={"answer": text, **body}
    )
    assert r.status_code == 201, r.text
    return r.json()


def edit(client, answer_id, **changes):
    with client.app.state.session_factory() as db:
        a = db.get(PracticeAnswer, answer_id)
        for k, v in changes.items():
            if k == "feedback":
                a.feedback = {**a.feedback, **v}
            elif k == "drop_feedback":
                a.feedback = {x: y for x, y in a.feedback.items() if x not in v}
            else:
                setattr(a, k, v)
        db.commit()


def question_page(client, h, qid):
    return {
        a["id"]: a["comparison"]
        for a in client.get(f"/api/v1/careers/{TRACK}/questions/{qid}/answers", headers=h).json()
    }


def chart_list(client, h, **params):
    items, offset = [], 0
    while True:
        r = client.get(
            f"/api/v1/me/careers/{TRACK}/analytics/attempts",
            headers=h,
            params={**params, "offset": offset, "limit": 2},
        )
        assert r.status_code == 200, r.text
        page = r.json()
        items += page["items"]
        offset += len(page["items"])
        if offset >= page["total"] or not page["items"]:
            return page, items


def test_the_same_pairs_read_the_same_on_the_question_page_and_in_the_chart(client):
    h = nurse(client)
    qid = "e-good-0"
    first = answer(client, h, qid, LONG)
    second = answer(client, h, qid, LONGER)  # comparable with the first
    third = answer(client, h, qid, SHORT)  # too short: partly comparable, no numbers
    fourth = answer(client, h, qid, LONGER)
    edit(
        client, fourth["id"], feedback={"rubric_version": "v9", "evaluator": "built-in (offline) · rubric v9"}
    )
    fifth = answer(client, h, qid, LONG)
    edit(client, fifth["id"], drop_feedback=("rubric_version", "evaluator"))  # rubric not recorded
    page = question_page(client, h, qid)
    _, listed = chart_list(client, h)
    chart = {i["answer_id"]: i["comparison"] for i in listed}
    for a in (first, second, third, fourth, fifth):
        assert page[a["id"]] == chart[a["id"]], a["id"]
    assert page[first["id"]] is None
    assert page[second["id"]]["outcome"] == "comparable" and page[second["id"]]["against"] == first["id"]
    assert (
        page[third["id"]]["outcome"] == "partially_comparable" and not page[third["id"]]["scores_comparable"]
    )
    assert "scored under different rubrics" in page[fourth["id"]]["explanation"]
    assert (
        page[fifth["id"]]["outcome"] == "unknown"
        and "which rubric graded one of them wasn't recorded" in page[fifth["id"]]["explanation"]
    )


def test_a_revision_is_compared_with_the_answer_it_revises_everywhere(client):
    h = nurse(client)
    qid = "e-good-0"
    first = answer(client, h, qid, LONG)
    answer(client, h, qid, SHORT)
    third = answer(client, h, qid, LONGER, revises_answer_id=first["id"])
    page = question_page(client, h, qid)
    _, listed = chart_list(client, h)
    chart = {i["answer_id"]: i["comparison"] for i in listed}
    assert page[third["id"]]["against"] == first["id"] == chart[third["id"]]["against"]
    assert page[third["id"]] == chart[third["id"]]


def test_recorded_help_is_named_in_both_places(client):
    from tests.test_attempt_conditions import read_lesson

    h = nurse(client)
    qid = "e-steps-7"  # a lesson prepares it (rn-sbar-handoff)
    answer(client, h, qid, LONG)
    read_lesson(client, h)  # read between the two answers: help before the second only
    second = answer(client, h, qid, LONGER)
    assert second["conditions"]["labels"] == ["Hint shown"]
    page = question_page(client, h, qid)
    _, listed = chart_list(client, h)
    c = page[second["id"]]
    assert c == {i["answer_id"]: i["comparison"] for i in listed}[second["id"]]
    assert c["outcome"] == "partially_comparable" and c["scores_comparable"]
    assert (
        "the in-app help differed: before the earlier one, none recorded; before the later one, hint shown"
        in c["explanation"]
    )


def test_an_interview_retry_reads_the_same_as_the_chart(client):
    from tests.test_review import STRONG, round_with

    h = nurse(client)
    first = STRONG.rsplit(" As a result", 1)[0] + " I stayed with him until the team arrived and handed over."
    iv = round_with(client, h, [first, None, None, None, None])
    retry = client.post(
        f"/api/v1/interviews/{iv}/questions/0/retries", headers=h, json={"answer": STRONG}
    ).json()
    _, listed = chart_list(client, h)
    chart = {i["answer_id"]: i["comparison"] for i in listed}
    assert retry["classification"] == chart[retry["latest"]["id"]]
    assert retry["comparability_note"] == chart[retry["latest"]["id"]]["explanation"]


def test_the_chart_counts_only_its_cohort_and_the_denominators_match(client):
    h = nurse(client)
    other = nurse(client, email="grace@example.com")
    a = answer(client, h, "e-good-0", LONG)
    answer(client, h, "e-good-0", SHORT)  # not counted: too short
    c = answer(client, h, "e-time-0", LONGER)
    d = answer(client, h, "e-time-0", LONG)
    edit(client, d["id"], drop_feedback=("rubric_version", "evaluator"))  # not counted: not recorded
    old = answer(client, h, "e-good-0", LONGER)
    edit(client, old["id"], created_at=datetime.now(UTC) - timedelta(days=60))
    answer(client, other, "e-good-0", LONG)  # another account's: never counted here
    today = datetime.now(UTC).date()

    def check(**params):
        analytics = client.get(f"/api/v1/me/careers/{TRACK}/analytics", headers=h, params=params).json()
        page, listed = chart_list(client, h, **params)
        in_trend = sum(s["attempts"] for s in analytics["trends"])
        assert in_trend == page["in_chart"] == sum(1 for i in listed if i["series"] is not None)
        assert all(sum(p["answers"] for p in s["points"]) == s["attempts"] for s in analytics["trends"])
        assert page["total"] == len(listed) == analytics["answers"]
        assert in_trend + sum(n["count"] for n in analytics["not_in_trend"]) == analytics["answers"]
        return analytics, listed

    analytics, listed = check(since=(today - timedelta(days=30)).isoformat())
    assert {i["answer_id"] for i in listed if i["series"]} == {a["id"], c["id"]}
    assert {n["reason"]: n["count"] for n in analytics["not_in_trend"]} == {
        "too short to score": 1,
        "which rubric graded it wasn't recorded": 1,
    }
    assert all(i["scale"] == "0-100" and isinstance(i["score"], int) for i in listed)
    analytics, listed = check()  # all time: the older answer joins the cohort
    assert old["id"] in {i["answer_id"] for i in listed if i["series"]}
    assert analytics["comparison_rules"] == CONTRACT_VERSION
    # A career filter: another career's answers aren't in this one.
    assert (
        client.get("/api/v1/me/careers/customer-service-representative/analytics/attempts", headers=h).json()[
            "total"
        ]
        == 0
    )


def test_another_accounts_answers_never_enter_a_cohort_or_a_comparison(client):
    h = nurse(client)
    other = nurse(client, email="grace@example.com")
    mine = answer(client, h, "e-good-0", LONG)
    theirs = answer(client, other, "e-good-0", LONGER)
    _, listed = chart_list(client, h)
    assert [i["answer_id"] for i in listed] == [mine["id"]] and listed[0]["comparison"] is None
    assert question_page(client, h, "e-good-0") == {mine["id"]: None}
    with client.app.state.session_factory() as db:
        assert db.scalar(
            select(PracticeAnswer.user_id).where(PracticeAnswer.id == theirs["id"])
        ) != db.scalar(select(PracticeAnswer.user_id).where(PracticeAnswer.id == mine["id"]))


def test_the_export_keeps_each_classification_with_its_rules_version(client):
    h = nurse(client)
    answer(client, h, "e-good-0", LONG)
    second = answer(client, h, "e-good-0", LONGER)
    doc = client.get("/api/v1/me/export", headers=h).json()
    exported = {a["id"]: a["comparison"] for a in doc["interview_answers"]}
    assert exported[second["id"]] == question_page(client, h, "e-good-0")[second["id"]]
    assert exported[second["id"]]["contract_version"] == CONTRACT_VERSION


def test_help_from_before_recording_began_is_unknown_not_none(client):
    h = nurse(client)
    qid = "e-good-0"
    old = answer(client, h, qid, LONG)
    edit(client, old["id"], created_at=datetime(2026, 11, 1, 9, tzinfo=UTC))  # before help was recorded
    new = answer(client, h, qid, LONGER)
    c = question_page(client, h, qid)[new["id"]]
    _, listed = chart_list(client, h)
    assert c == {i["answer_id"]: i["comparison"] for i in listed}[new["id"]]
    assert c["outcome"] == "unknown" and [r["rule"] for r in c["reasons"]] == ["help"]
    assert (
        "in-app help before one of them wasn't recorded (it's recorded from 14 Nov 2026)" in c["explanation"]
    )
