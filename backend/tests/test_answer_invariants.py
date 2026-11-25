"""The read-only answer diagnostic (Release Readiness brief 11): one synthetic violation per rule,
valid controls that stay clean, unknowns kept apart, and nothing written or printed that it
shouldn't. Synthetic data only."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

from app.careers.questions import questions_for
from app.models import PracticeAnswer
from app.services.answer_invariants import NOTICES, VIOLATIONS, Row, check, check_rows
from tests.conftest import auth_headers, register

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def row(id: str, **over) -> Row:
    base = dict(
        id=id,
        user_id="u1",
        track="registered-nurse",
        question_id="q1",
        created_at=T0,
        key=None,
        fingerprint=None,
        parent=None,
        eligibility="scored",
        sql_too_short=False,
    )
    base.update(over)
    return Row(**base)


CONTROLS = [
    row("ok-low", eligibility="scored"),  # a valid score of 0 or 35 is a score: the rule never looks at it
    row("ok-short", eligibility="too_short", sql_too_short=True),
    row("ok-key", key="op-shared-0001", fingerprint="v1:abc"),
    row("ok-key-other-owner", user_id="u2", key="op-shared-0001", fingerprint="v1:def"),  # not a duplicate
    row("ok-parent", created_at=T0 - timedelta(hours=1)),
    row("ok-revision", parent="ok-parent"),
]


def test_valid_controls_are_clean():
    rep = check_rows(CONTROLS)
    assert rep.ok and not any(rep.found.values())
    assert rep.summary()["scope"] == {"answers_inspected": len(CONTROLS), "accounts": 2}


def test_each_rule_finds_its_one_violation():
    bad = {
        "duplicate_key": [
            row("d1", key="op-dup-00001", fingerprint="v1:a"),
            row("d2", key="op-dup-00001", fingerprint="v1:b"),
        ],
        "key_without_fingerprint": [row("k1", key="op-nofp-0001")],
        "fingerprint_without_key": [row("f1", fingerprint="v1:x")],
        "parent_missing": [row("m1", parent="gone")],
        "parent_self": [row("s1", parent="s1")],
        "parent_other_owner": [row("o1", parent="ok-parent", user_id="u2")],
        "parent_other_question": [row("x1", parent="ok-parent", question_id="q2")],
        "parent_newer": [
            row("n1", parent="later", created_at=T0),
            row("later", created_at=T0 + timedelta(days=1)),
        ],
        "eligibility_sql_mismatch": [row("e1", eligibility="too_short", sql_too_short=False)],
    }
    assert set(bad) == set(VIOLATIONS)
    for rule, rows in bad.items():
        rep = check_rows(CONTROLS + rows)
        flagged = {k for k, v in rep.found.items() if v}
        assert flagged == {rule}, (rule, flagged)
        assert not rep.ok


def test_unknowns_are_notices_not_violations_and_never_scores():
    rep = check_rows(
        CONTROLS + [row("u", eligibility="unknown"), row("v0", key="op-old-version", fingerprint="v0:zz")]
    )
    assert rep.ok
    assert {k for k, v in rep.found.items() if v} == set(NOTICES)
    assert rep.summary()["notices"]["eligibility_unknown"] == {"count": 1, "ids": [("u", "u1")]}


def test_on_a_real_database_it_reads_only_and_prints_no_text_or_keys(client):
    h = auth_headers(register(client))
    qid = questions_for("registered-nurse")[0].id
    url = f"/api/v1/careers/registered-nurse/questions/{qid}/answers"
    secret_text = "Last winter on a busy ward I noticed a patient's breathing change " * 3
    first = client.post(
        url, headers=h, json={"answer": secret_text, "client_request_id": "op-private-key-1"}
    ).json()
    client.post(url, headers=h, json={"answer": secret_text + " More.", "revises_answer_id": first["id"]})
    client.post(url, headers=h, json={"answer": "I would check the patient and call the doctor."})
    db = client.app.state.session_factory()
    template = db.query(PracticeAnswer).first()
    fb = copy.deepcopy(template.feedback)
    fb.pop("evidence_level", None)
    fb.pop("word_count", None)
    db.add(
        PracticeAnswer(
            user_id=template.user_id,
            track=template.track,
            question_id=qid,
            difficulty="easy",
            answer="(legacy)",
            score=50,
            feedback=fb,
            provider=template.provider,
            content_version=1,
        )
    )
    db.commit()
    before = [(r.id, r.revises_answer_id, r.client_request_id) for r in db.query(PracticeAnswer).all()]
    rep = check(db)
    after = [(r.id, r.revises_answer_id, r.client_request_id) for r in db.query(PracticeAnswer).all()]
    db.close()
    assert before == after and rep.ok and rep.inspected == 4
    out = repr(rep.summary())
    assert secret_text[:20] not in out and "op-private-key-1" not in out
    assert rep.summary()["notices"]["eligibility_unknown"]["count"] == 1
