"""Content quality: trust labels from recorded evidence, version-pinned reports, duplicate
grouping, admin-only triage with an audit trail, corrections as new versions, retirement, and
the validation command."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.content import state as content_state
from app.content.validate import run as validate_content
from app.models import ContentAudit, ContentCheck, ContentReport, ContentStatus, ContentVersion, User
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
QID = "m-pressure-0"
KEY = f"{NURSE}/{QID}"
ANSWER = "Last winter a patient deteriorated. I assessed him, called the rapid response team and he was stable in 30 minutes."


def nurse(client, email="ada@example.com", name="Ada"):
    return auth_headers(register(client, email=email, display_name=name, career_track=NURSE))


def admin(client, email="root@example.com"):
    h = nurse(client, email=email, name="Triage")
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == email)).is_admin = True
        db.commit()
    return h


def report(client, h, **body):
    payload = {
        "content_type": "question",
        "content_id": KEY,
        "content_version": 1,
        "category": "ambiguous_wording",
        "details": "Unclear.",
        **body,
    }
    return client.post("/api/v1/reports", headers=h, json=payload)


def meta(client, content_type="question", content_id=KEY):
    r = client.get(f"/api/v1/content/{content_type}/{content_id}/meta")
    assert r.status_code == 200, r.text
    return r.json()


def test_trust_labels_come_only_from_recorded_evidence(client):
    m = meta(client)
    assert m["version"] == 1 and m["status"] == "active" and m["career"] == "Registered Nurse"
    assert [label["key"] for label in m["labels"]] == ["generated", "not_expert_reviewed"]
    p = meta(client, "problem", "two-sum")
    assert [label["key"] for label in p["labels"]] == [
        "generated",
        "tests_not_checked",
        "not_expert_reviewed",
    ]
    assert p["version_label"] == "Test version 1"

    def record(passed, version):
        with client.app.state.session_factory() as db:
            row = db.scalar(select(ContentCheck).where(ContentCheck.content_id == "two-sum")) or ContentCheck(
                content_type="problem", content_id="two-sum", check="reference_solution"
            )
            row.passed, row.content_version, row.checked_at = (
                passed,
                version,
                datetime(2026, 11, 3, tzinfo=UTC),
            )
            db.add(row)
            db.commit()

    record(False, 1)
    assert "reference_verified" not in [x["key"] for x in meta(client, "problem", "two-sum")["labels"]]
    record(True, 0)  # passed, but against older tests
    assert "reference_verified" not in [x["key"] for x in meta(client, "problem", "two-sum")["labels"]]
    record(True, 1)
    labels = meta(client, "problem", "two-sum")["labels"]
    assert labels[1]["key"] == "reference_verified" and "checked Nov 03, 2026" in labels[1]["text"]
    assert all("expert" not in x["text"] or x["key"] == "not_expert_reviewed" for x in labels)


def test_reports_are_pinned_to_a_version_and_stored_as_plain_text(client):
    h = nurse(client)
    r = report(
        client, h, details="<script>alert(1)</script>\x00 The word 'stable' is vague.", excerpt="  my words  "
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["content_version"] == 1 and body["status"] == "open" and body["content_title"]
    assert (
        body["details"] == "<script>alert(1)</script> The word 'stable' is vague."
        and body["excerpt"] == "my words"
    )
    assert report(client, h, content_version=2).json()["error"]["code"] == "invalid_version"
    assert report(client, h, content_id=f"{NURSE}/no-such").status_code == 404
    assert report(client, h, category="nonsense").status_code == 422
    assert report(client, h, details="x" * 2001).status_code == 422
    again = report(client, h)
    assert again.status_code == 409 and again.json()["error"]["details"]["report_id"] == body["id"]
    assert client.post("/api/v1/reports", json={}).status_code in (401, 422)


def test_feedback_reports_need_your_own_answer_and_attach_nothing_automatically(client):
    h = nurse(client)
    a = client.post(
        f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=h, json={"answer": ANSWER}
    ).json()
    other = nurse(client, "bea@example.com", "Bea")
    assert (
        report(client, other, context="feedback", answer_id=a["id"], category="incorrect_example").status_code
        == 404
    )
    assert (
        report(client, h, context="feedback", category="incorrect_example").json()["error"]["code"]
        == "answer_required"
    )
    r = report(client, h, context="feedback", answer_id=a["id"], category="incorrect_example")
    assert r.status_code == 201 and r.json()["excerpt"] is None  # the answer isn't copied unless chosen
    with client.app.state.session_factory() as db:
        row = db.scalars(select(ContentReport)).one()
        assert row.answer_id == a["id"] and ANSWER not in (row.details + (row.excerpt or ""))


def test_duplicates_are_grouped_not_deleted_and_reports_are_rate_limited(client, make_client):
    first = report(client, nurse(client)).json()
    second = report(client, nurse(client, "bea@example.com", "Bea")).json()
    other_category = report(client, nurse(client, "cy@example.com", "Cy"), category="accessibility").json()
    with client.app.state.session_factory() as db:
        rows = {r.id: r for r in db.scalars(select(ContentReport))}
    assert len(rows) == 3 and rows[second["id"]].duplicate_of == first["id"]
    assert rows[other_category["id"]].duplicate_of is None

    limited = make_client(content_reports_per_hour=2)
    h = nurse(limited, "dee@example.com", "Dee")
    codes = [
        report(limited, h, category=c).status_code for c in ("outdated_guidance", "technical_bug", "other")
    ]
    assert codes == [201, 201, 429]


def test_admin_routes_are_invisible_to_everyone_else(client):
    h = nurse(client)
    rid = report(client, h).json()["id"]
    calls = [
        ("GET", "/api/v1/admin/reports", None),
        ("GET", f"/api/v1/admin/reports/{rid}", None),
        ("POST", f"/api/v1/admin/reports/{rid}/status", {"status": "investigating"}),
        ("POST", f"/api/v1/admin/reports/{rid}/duplicate", {"duplicate_of": None}),
        (
            "POST",
            f"/api/v1/admin/content/question/{NURSE}/{QID}/corrections",
            {"prompt": "A new prompt for this question.", "change_note": "Clearer."},
        ),
        ("POST", f"/api/v1/admin/content/question/{KEY}/retire", {"reason": "Broken question."}),
        ("POST", f"/api/v1/admin/content/question/{KEY}/restore", {}),
    ]
    for headers in ({}, h):
        for method, path, body in calls:
            r = client.request(method, path, headers=headers, json=body)
            assert r.status_code == 404, (method, path, r.status_code)
    assert client.get("/api/v1/auth/me", headers=h).json()["is_admin"] is False
    assert meta(client)["version"] == 1 and meta(client)["status"] == "active"  # nothing changed


def test_triage_statuses_are_audited_and_reporters_see_only_the_public_outcome(client):
    ada, bea = nurse(client), nurse(client, "bea@example.com", "Bea")
    a = client.post(
        f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER}
    ).json()
    first = report(client, ada).json()
    second = report(client, bea).json()
    root = admin(client)
    groups = client.get("/api/v1/admin/reports?status=open", headers=root).json()
    assert len(groups) == 1 and groups[0]["open_count"] == 2
    assert (
        groups[0]["reports"][0]["duplicates"] == [second["id"]]
        and groups[0]["reports"][0]["reporter"] == "Ada"
    )
    assert "@" not in str(groups)  # never an email

    r = client.post(f"/api/v1/admin/reports/{first['id']}/status", headers=root, json={"status": "resolved"})
    assert r.json()["error"]["code"] == "resolution_required"
    client.post(
        f"/api/v1/admin/reports/{first['id']}/status",
        headers=root,
        json={"status": "investigating", "internal_note": "Looks real."},
    )
    done = client.post(
        f"/api/v1/admin/reports/{first['id']}/status",
        headers=root,
        json={
            "status": "not_actionable",
            "resolution": "The wording matches the career profile.",
            "internal_note": "Discussed.",
        },
    ).json()
    assert done["status"] == "not_actionable" and [e["action"] for e in done["audit"]][:1] == ["reported"]
    assert any(e["internal_note"] == "Looks real." and e["actor"] == "Triage" for e in done["audit"])

    for h, mine in ((ada, first), (bea, second)):
        rows = client.get("/api/v1/me/reports", headers=h).json()
        assert [x["id"] for x in rows] == [mine["id"]]  # only their own
        assert (
            rows[0]["status"] == "not_actionable"
            and rows[0]["resolution"] == "The wording matches the career profile."
        )
        assert "Looks real" not in str(rows) and "Discussed" not in str(rows)
    # A report never touches a score.
    assert (
        client.get(f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada).json()[0]["score"]
        == a["score"]
    )


def test_grouping_can_be_changed_but_only_within_the_same_content(client):
    one = report(client, nurse(client)).json()
    two = report(client, nurse(client, "bea@example.com", "Bea"), category="other").json()
    elsewhere = report(client, nurse(client, "cy@example.com", "Cy"), content_id=f"{NURSE}/e-good-0").json()
    root = admin(client)
    grouped = client.post(
        f"/api/v1/admin/reports/{two['id']}/duplicate", headers=root, json={"duplicate_of": one["id"]}
    ).json()
    assert grouped["duplicate_of"] == one["id"]
    bad = client.post(
        f"/api/v1/admin/reports/{elsewhere['id']}/duplicate", headers=root, json={"duplicate_of": one["id"]}
    )
    assert bad.json()["error"]["code"] == "invalid_duplicate"
    ungrouped = client.post(
        f"/api/v1/admin/reports/{two['id']}/duplicate", headers=root, json={"duplicate_of": None}
    ).json()
    assert ungrouped["duplicate_of"] is None
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(ContentReport)).all()) == 3  # nothing deleted


def test_a_correction_is_a_new_version_and_old_answers_keep_theirs(client):
    ada = nurse(client)
    old = client.post(
        f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER}
    ).json()
    client.put(
        "/api/v1/me/bookmarks", headers=ada, json={"item_type": "question", "track": NURSE, "ref_id": QID}
    )
    before_prompt = client.get(f"/api/v1/careers/{NURSE}/questions/{QID}").json()["prompt"]
    rid = report(client, ada).json()["id"]
    bea = nurse(client, "bea@example.com", "Bea")
    assert report(client, bea).status_code == 201  # grouped under Ada's
    root = admin(client)
    bad = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/corrections",
        headers=root,
        json={"prompt": before_prompt, "change_note": "No-op."},
    )
    assert bad.json()["error"]["code"] == "no_change"
    new_prompt = (
        "Tell me about a time you assessed a patient under pressure: what did you check first, and why?"
    )
    m = client.post(
        f"/api/v1/admin/content/question/{NURSE}/{QID}/corrections",
        headers=root,
        json={"prompt": new_prompt, "change_note": "Says what we want to hear about.", "report_ids": [rid]},
    ).json()
    assert m["version"] == 2 and m["changes"][0]["note"] == "Says what we want to hear about."
    assert "corrected" in [x["key"] for x in m["labels"]]
    q = client.get(f"/api/v1/careers/{NURSE}/questions/{QID}").json()
    assert q["prompt"] == new_prompt
    v1 = client.get(f"/api/v1/careers/{NURSE}/questions/{QID}/versions/1").json()
    assert v1["prompt"] == before_prompt
    assert client.get(f"/api/v1/careers/{NURSE}/questions/{QID}/versions/3").status_code == 404
    # The old answer is unchanged and still says which version it answered; a new one is version 2.
    answers = client.get(f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada).json()
    assert answers[0] == old and answers[0]["content_version"] == 1
    new = client.post(
        f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER}
    ).json()
    assert new["content_version"] == 2
    mine = client.get("/api/v1/me/reports", headers=ada).json()[0]
    assert mine["status"] == "resolved" and mine["resolution"].startswith("Corrected in version 2:")
    # Someone who reported the same thing (grouped as a likely duplicate) hears the outcome too.
    dup = client.get("/api/v1/me/reports", headers=bea).json()[0]
    assert dup["status"] == "resolved" and dup["resolution"] == mine["resolution"]
    with client.app.state.session_factory() as db:
        assert db.scalars(select(ContentVersion)).one().created_by is not None
        assert "corrected" in [a.action for a in db.scalars(select(ContentAudit))]
        from app.models import Bookmark

        assert db.scalars(select(Bookmark)).one().content_version == 1


def test_retirement_keeps_history_readable_and_stops_practice(client):
    ada = nurse(client)
    client.post(f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER})
    client.put(
        "/api/v1/me/bookmarks", headers=ada, json={"item_type": "question", "track": NURSE, "ref_id": QID}
    )
    root = admin(client)
    m = client.post(
        f"/api/v1/admin/content/question/{KEY}/retire",
        headers=root,
        json={"reason": "The scenario was misleading."},
    ).json()
    assert m["status"] == "retired" and m["retired_reason"] == "The scenario was misleading."
    # No longer offered for practice...
    listing = client.get(f"/api/v1/careers/{NURSE}/questions?difficulty=medium&page_size=100").json()
    assert QID not in [x["id"] for x in listing["items"]]
    r = client.post(f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER})
    assert r.status_code == 409 and r.json()["error"]["code"] == "content_retired"
    # ...but still readable, in history and in saved items, with the reason.
    assert client.get(f"/api/v1/careers/{NURSE}/questions/{QID}").status_code == 200
    assert len(client.get(f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada).json()) == 1
    mark = client.get("/api/v1/me/bookmarks", headers=ada).json()[0]
    assert mark["available"] is False and mark["href"].endswith(QID)
    # Restore.
    client.post(f"/api/v1/admin/content/question/{KEY}/restore", headers=root, json={})
    assert meta(client)["status"] == "active"
    assert (
        client.post(
            f"/api/v1/careers/{NURSE}/questions/{QID}/answers", headers=ada, json={"answer": ANSWER}
        ).status_code
        == 201
    )


def test_a_retired_problem_leaves_the_library_and_cannot_be_submitted(client):
    h = auth_headers(register(client))
    root = admin(client)
    client.post(
        "/api/v1/admin/content/problem/two-sum/retire",
        headers=root,
        json={"reason": "A test case was wrong."},
    )
    slugs = [p["slug"] for p in client.get("/api/v1/problems?page_size=100").json()["items"]]
    assert "two-sum" not in slugs
    assert client.get("/api/v1/problems/two-sum").status_code == 200
    r = client.post(
        "/api/v1/submissions",
        headers=h,
        json={"problem_slug": "two-sum", "language": "java", "source_code": "class Solution {}"},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "content_retired"
    recs = [x["slug"] for x in client.get("/api/v1/me/recommendations?limit=20", headers=h).json()]
    assert "two-sum" not in recs


def test_the_validation_command_passes_the_real_bank_and_catches_broken_records(client):
    with client.app.state.session_factory() as db:
        ok = validate_content(db)
        assert ok.ok, ok.errors[:5]
        assert ok.counts["questions"] > 1000 and ok.counts["problems"] >= 300
        db.add(
            ContentVersion(
                content_type="question", content_id=KEY, version=3, fields={"rubric": "x"}, change_note=" "
            )
        )
        db.add(ContentStatus(content_type="problem", content_id="no-such-problem", reason="gone"))
        db.commit()
        bad = validate_content(db)
    text = "\n".join(bad.errors)
    assert "fields that can't be corrected" in text and "no change note" in text
    assert "should run 2, 3" in text and "no-such-problem: content doesn't exist" in text
    content_state.invalidate()


def test_reports_are_exported_and_deleted_with_the_account(client):
    h = nurse(client)
    report(client, h, details="Unclear wording.")
    assert (
        client.get("/api/v1/me/export", headers=h).json()["content_reports"][0]["details"]
        == "Unclear wording."
    )
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert db.scalars(select(ContentReport)).all() == []


def test_admin_is_granted_and_revoked_only_from_the_command_line(client, monkeypatch, capsys):
    from app.cli import main as cli_main
    from app.config import get_settings

    h = nurse(client, email="ops@example.com", name="Ops")
    assert client.get("/api/v1/admin/reports", headers=h).status_code == 404
    monkeypatch.setenv("DATABASE_URL", client.app.state.settings.database_url)
    get_settings.cache_clear()
    try:
        assert cli_main(["app.cli", "grant-admin", "  OPS@Example.com "]) == 0
        assert client.get("/api/v1/admin/reports", headers=h).status_code == 200
        assert client.get("/api/v1/auth/me", headers=h).json()["is_admin"] is True
        assert cli_main(["app.cli", "revoke-admin", "ops@example.com"]) == 0
        assert client.get("/api/v1/admin/reports", headers=h).status_code == 404
        assert cli_main(["app.cli", "grant-admin", "nobody@example.com"]) == 1
        assert cli_main(["app.cli", "grant-admin"]) == 1
    finally:
        get_settings.cache_clear()
    out = capsys.readouterr().out
    assert "ops@example.com: admin granted" in out and "ops@example.com: admin revoked" in out
    assert "No registered account has that email." in out
