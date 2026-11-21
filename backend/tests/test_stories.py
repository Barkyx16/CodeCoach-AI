"""The story bank: one shared model with job targets, every save kept, writing help that only
proposes and never invents, practice that never overwrites the story, and strict privacy."""

import json
import re

from sqlalchemy import select

from app.models import ExperienceEntry, StoryRevision
from app.services import story_assist
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
URL = "/api/v1/me/stories"
STORY = {
    "title": "Two call lights at once",
    "track": NURSE,
    "context": "work",
    "situation": "On a night shift two patients rang at the same time.",
    "task": "I had to decide who to see first.",
    "action": "I checked which patient was at higher risk, asked a colleague to check the other, and saw the first patient.",
    "result": "Both patients were seen within five minutes and nobody came to harm.",
    "competencies": ["prioritization", "teamwork"],
    "tags": ["night shift"],
}
QUESTION = f"/api/v1/careers/{NURSE}/questions/m-pressure-0/answers"


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def create(client, h, **over):
    r = client.post(URL, headers=h, json={**STORY, **over})
    assert r.status_code == 201, r.text
    return r.json()


def patch(client, h, sid, **body):
    return client.patch(f"{URL}/{sid}", headers=h, json=body)


def test_writing_editing_and_every_saved_version(client):
    h = nurse(client)
    s = create(client, h)
    assert s["revision"] == 1 and s["missing"] == [] and s["competencies"] == ["prioritization", "teamwork"]
    edited = patch(
        client, h, s["id"], expected_revision=1, result="Both patients were seen within five minutes."
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    # Another tab still holding revision 1 can't overwrite it.
    stale = patch(client, h, s["id"], expected_revision=1, title="Older tab")
    assert stale.status_code == 409 and stale.json()["error"]["details"]["current_revision"] == 2
    # Saving nothing new doesn't make a revision.
    assert patch(client, h, s["id"], expected_revision=2, title=STORY["title"]).json()["revision"] == 2

    revs = client.get(f"{URL}/{s['id']}/revisions", headers=h).json()
    assert [(r["revision"], r["reason"]) for r in revs] == [(2, "edited"), (1, "created")]
    assert revs[1]["fields"]["result"] == STORY["result"]
    restored = client.post(f"{URL}/{s['id']}/revisions/1/restore", headers=h, json={"expected_revision": 2})
    assert restored.status_code == 200
    assert restored.json()["result"] == STORY["result"] and restored.json()["revision"] == 3
    assert [r["reason"] for r in client.get(f"{URL}/{s['id']}/revisions", headers=h).json()] == [
        "restored",
        "edited",
        "created",
    ]
    assert (
        client.post(
            f"{URL}/{s['id']}/revisions/9/restore", headers=h, json={"expected_revision": 3}
        ).status_code
        == 404
    )


def test_missing_sections_are_pointed_out_without_judgment(client):
    h = nurse(client)
    s = create(client, h, task="", action="", result="", reflection="")
    assert s["missing"] == ["task", "action", "result"]
    assert s["preview"].startswith("On a night shift")


def test_job_target_examples_and_the_story_bank_are_the_same_stories(client):
    h = nurse(client)
    t = client.post(
        "/api/v1/targets",
        headers=h,
        json={"title": "Ward nurse", "description": "Prioritise patient care. Work in a team."},
    ).json()
    client.post(
        f"/api/v1/targets/{t['id']}/experience",
        headers=h,
        json={
            "title": "Busy ward",
            "situation": "Short-staffed.",
            "action": "I reorganised breaks.",
            "result": "Every patient was covered.",
        },
    )
    stories = client.get(URL, headers=h).json()
    assert (
        len(stories) == 1
        and stories[0]["target"] == {"id": t["id"], "title": "Ward nurse"}
        and stories[0]["track"] == NURSE
    )
    sid = stories[0]["id"]
    # One copy: editing it in the story bank changes it in the target too.
    patch(
        client,
        h,
        sid,
        expected_revision=1,
        title="Busy ward, short-staffed",
        task="Keep every patient covered.",
    )
    target = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    assert [e["title"] for e in target["experience"]] == ["Busy ward, short-staffed"]
    # Editing it in the target keeps a revision too, and keeps what only the story bank shows.
    entry_id = target["experience"][0]["id"]
    client.put(
        f"/api/v1/targets/{t['id']}/experience/{entry_id}",
        headers=h,
        json={
            "title": "Busy ward",
            "situation": "Short-staffed.",
            "action": "I reorganised breaks.",
            "result": "Every patient was covered.",
        },
    )
    story = client.get(f"{URL}/{sid}", headers=h).json()
    assert story["revision"] == 3 and story["task"] == "Keep every patient covered."
    # Deleting the target unlinks the story; it never deletes it.
    assert client.delete(f"/api/v1/targets/{t['id']}", headers=h).status_code == 204
    story = client.get(f"{URL}/{sid}", headers=h).json()
    assert story["target"] is None and story["title"] == "Busy ward"


def test_links_use_stable_ids_and_are_checked(client):
    h = nurse(client)
    other = nurse(client, email="bea@example.com")
    s = create(client, h)
    bad = patch(client, h, s["id"], expected_revision=1, question_refs=[f"{NURSE}/no-such-question"])
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_question"
    linked = patch(client, h, s["id"], expected_revision=1, question_refs=[f"{NURSE}/m-pressure-0"]).json()
    assert (
        linked["questions"][0]["href"] == f"/careers/{NURSE}/questions/m-pressure-0"
        and linked["questions"][0]["available"]
    )
    theirs = client.post(
        "/api/v1/targets", headers=other, json={"title": "Not yours", "description": "Teamwork."}
    ).json()
    assert patch(client, h, s["id"], expected_revision=2, target_id=theirs["id"]).status_code == 404
    mine = client.post(
        "/api/v1/targets", headers=h, json={"title": "Mine", "description": "Teamwork."}
    ).json()
    assert (
        patch(client, h, s["id"], expected_revision=2, target_id=mine["id"]).json()["target"]["title"]
        == "Mine"
    )
    assert patch(client, h, s["id"], expected_revision=3, clear_target=True).json()["target"] is None


def test_writing_help_only_proposes_and_never_invents(client):
    h = nurse(client)
    s = create(
        client,
        h,
        action="Basically we really just reorganised the rota. We kind of helped with the handover. We reorganised the rota.",
        result="",
    )
    check = client.post(f"{URL}/{s['id']}/assist", headers=h, json={"action": "check"}).json()
    assert "rules, not AI" in check["method"] and check["proposals"] == []
    assert any("Which parts did you do yourself" in q for q in check["questions"])
    assert any(q.startswith("Result:") and "number isn't required" in q for q in check["questions"])
    short = client.post(f"{URL}/{s['id']}/assist", headers=h, json={"action": "shorten"}).json()
    (p,) = [p for p in short["proposals"] if p["field"] == "action"]
    assert p["proposed"] == "We reorganised the rota. We helped with the handover."
    assert any("repeated sentence" in c for c in p["changes"])
    clarity = client.post(f"{URL}/{s['id']}/assist", headers=h, json={"action": "clarity"}).json()
    assert any("helped with" in q for q in clarity["questions"])
    # Unsaved editor text can be checked too; nothing is saved by asking.
    unsaved = client.post(
        f"{URL}/{s['id']}/assist",
        headers=h,
        json={"action": "shorten", "situation": "It was really very busy."},
    ).json()
    assert [p["proposed"] for p in unsaved["proposals"] if p["field"] == "situation"] == ["It was busy."]
    assert client.get(f"{URL}/{s['id']}", headers=h).json()["revision"] == 1
    # Accepting is an ordinary save, recorded as assisted.
    patch(client, h, s["id"], expected_revision=1, action=p["proposed"], reason="assisted")
    assert client.get(f"{URL}/{s['id']}/revisions", headers=h).json()[0]["reason"] == "assisted"


def test_no_proposal_ever_adds_a_word_or_a_number():
    samples = [
        "I think I basically led the team of 12 nurses, really.",
        "In order to cut waiting times we sort of changed triage. In order to cut waiting times we sort of changed triage.",
        "I guess the result was a bit better: 30% fewer complaints, to be honest.",
        "At the end of the day, I just literally fixed it in order to ship.",
    ]
    for text in samples:
        sections = {"action": text}
        for p in story_assist.shorten(sections) + story_assist.clarity(sections)[0]:
            original = {w.lower() for w in story_assist.words(text)}
            assert all(w.lower() in original for w in story_assist.words(p.proposed)), (text, p.proposed)
            assert re.findall(r"\d+", p.proposed) == [n for n in re.findall(r"\d+", text) if n in p.proposed]
            assert len(p.proposed) < len(text)


def test_practising_a_story_records_a_separate_answer_and_never_changes_the_story(client):
    h = nurse(client)
    s = create(client, h)
    answer = "On a night shift two patients rang at once. I checked who was at higher risk, asked a colleague to help, and both were seen within five minutes."
    r = client.post(QUESTION, headers=h, json={"answer": answer, "story_id": s["id"]})
    assert r.status_code == 201 and r.json()["story_id"] == s["id"]
    story = client.get(f"{URL}/{s['id']}", headers=h).json()
    assert story["revision"] == 1 and story["action"] == STORY["action"]
    assert story["practice_count"] == 1 and story["practice"][0]["href"].endswith(f"?answer={r.json()['id']}")
    # Someone else's story can't be attached.
    other = nurse(client, email="bea@example.com")
    assert (
        client.post(QUESTION, headers=other, json={"answer": answer, "story_id": s["id"]}).status_code == 404
    )
    # Deleting the story keeps the answer and its score.
    assert client.delete(f"{URL}/{s['id']}", headers=h).status_code == 204
    kept = client.get(QUESTION, headers=h).json()
    assert len(kept) == 1 and kept[0]["story_id"] is None and kept[0]["score"] == r.json()["score"]


def test_a_shared_practice_answer_shows_nothing_from_the_story(client):
    h = nurse(client)
    s = create(
        client, h, notes="PRIVATE NOTE: ask Sam before using this.", evidence="EVIDENCE: audit report 2025"
    )
    a = client.post(
        QUESTION,
        headers=h,
        json={
            "answer": "Two patients rang at once. I triaged by risk and both were safe.",
            "story_id": s["id"],
        },
    ).json()
    preview = client.post("/api/v1/me/shares/preview", headers=h, json={"answer_id": a["id"]}).json()
    dumped = json.dumps(preview)
    assert "PRIVATE NOTE" not in dumped and "EVIDENCE" not in dumped and s["id"] not in dumped


def test_untrusted_text_limits_and_privacy_hints(client):
    h = nurse(client)
    s = create(
        client, h, title="<script>alert(1)</script>\x00 Title", situation="Mr. Smith (MRN 12345678) fell.\x07"
    )
    assert s["title"] == "<script>alert(1)</script> Title"  # stored as plain text, control characters removed
    assert s["situation"] == "Mr. Smith (MRN 12345678) fell."
    hints = " ".join(s["privacy_hints"])
    assert "“Mr. Smith” may identify someone" in hints and "12345678" in hints
    for bad in (
        {"competencies": ["genius"]},
        {"situation": "x" * 4001},
        {"tags": [str(i) for i in range(13)]},
        {"title": ""},
        {"track": "astronaut"},
    ):
        r = client.post(URL, headers=h, json={**STORY, **bad})
        assert r.status_code in (400, 422), bad


def test_stories_are_private(client):
    a = nurse(client)
    b = nurse(client, email="bea@example.com")
    s = create(client, a)
    assert client.get(URL, headers=b).json() == []
    for method, path, body in [
        ("GET", f"{URL}/{s['id']}", None),
        ("PATCH", f"{URL}/{s['id']}", {"expected_revision": 1, "title": "Mine now"}),
        ("GET", f"{URL}/{s['id']}/revisions", None),
        ("POST", f"{URL}/{s['id']}/revisions/1/restore", {"expected_revision": 1}),
        ("POST", f"{URL}/{s['id']}/assist", {"action": "check"}),
        ("POST", f"{URL}/{s['id']}/archive", None),
        ("DELETE", f"{URL}/{s['id']}", None),
    ]:
        assert client.request(method, path, headers=b, json=body).status_code == 404, path
    assert client.get(f"{URL}/{s['id']}", headers=a).json()["title"] == STORY["title"]
    assert client.get(URL).status_code == 401


def test_archiving_and_the_export_and_deletion(client):
    h = nurse(client)
    s = create(client, h)
    client.post(f"{URL}/{s['id']}/archive", headers=h)
    assert client.get(URL, headers=h).json() == []
    assert [x["id"] for x in client.get(f"{URL}?archived=true", headers=h).json()] == [s["id"]]
    client.post(f"{URL}/{s['id']}/unarchive", headers=h)
    patch(client, h, s["id"], expected_revision=1, reflection="Ask for help earlier.")
    client.post(
        QUESTION, headers=h, json={"answer": "Two patients rang. I triaged by risk.", "story_id": s["id"]}
    )
    exported = client.get("/api/v1/me/export", headers=h).json()
    (story,) = exported["stories"]
    assert story["reflection"] == "Ask for help earlier." and [r["revision"] for r in story["revisions"]] == [
        1,
        2,
    ]
    assert exported["interview_answers"][0]["story"] == s["id"]
    client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(select(ExperienceEntry)).all() == [] and db.scalars(select(StoryRevision)).all() == []
        )
