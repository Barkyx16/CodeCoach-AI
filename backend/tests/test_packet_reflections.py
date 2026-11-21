"""Real-interview reflections in the practice packet (Volume 14, prompt 8; docs/PACKET.md): listed
with only whether each has private details; chosen part by part; what was noticed and the
interviewers' names left out unless chosen, and the preview says what was left out; a story it
names read now by id, or "deleted since"; another account's or a deleted reflection is "not
found"; beside its interview's kit, not repeated. Nothing is stored or edited. Synthetic data only."""

from sqlalchemy import select

from app.models import InterviewReflection
from tests.test_packet import packet
from tests.test_packet_plans import a_kit, item, text_of
from tests.test_reflections import APPS, REFLECTION, event, nurse

SECRET = "CANARY-reflection-notes-5e1b2-not-a-real-secret"
PREVIEW = "/api/v1/me/packet/preview"
LIST = "/api/v1/me/packet/reflections"


def a_story(client, h, title="Two call lights"):
    r = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": title, "track": "registered-nurse", "short_version": "I triaged two calls at once."},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def reflect(client, h, ev_url, **over):
    body = {
        **REFLECTION,
        "observations": [
            {"text": "They asked for another example", "kind": "observed"},
            {"text": f"They disliked me {SECRET}", "kind": "interpretation"},
        ],
        "expected_revision": 0,
        **over,
    }
    r = client.put(ev_url, headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def reflection_item(client, h, ev_id, parts=None, **body):
    out = packet(
        client, h, [{"type": "reflection", "id": ev_id, **({"parts": parts} if parts else {})}], **body
    )
    assert out.status_code == 200, out.text
    return out.json()


def test_a_reflection_gives_its_parts_and_never_what_was_noticed_unless_chosen(client):
    h = nurse(client)
    sid = a_story(client, h)
    a, ev, url = event(client, h)
    before = reflect(client, h, url, story_ids=[sid])
    out = reflection_item(client, h, ev["id"])
    it = item(out, "reflection")
    assert it["title"] == "Reflection on Panel interview: Ward nurse at Mercy General"
    assert [s["heading"] for s in it["sections"]] == [
        "What you were asked",
        "What went well",
        "What to do differently",
        "What you said you'd follow up",
        "Stories you used",
    ]
    assert all(s["kind"] == "your_reflection" for s in it["sections"])
    text = text_of(it)
    assert "- How would you handle a medication error?" in text and "Topics: patient assessment" in text
    assert "My opening about the ward" in text and "Send my references by Friday" in text
    assert (
        "- Two call lights (your story, revision 1, read now)" in text
        and "I triaged two calls at once." in text
    )
    assert (
        "Your reflection on Panel interview (Ward nurse at Mercy General, 12 November 2026)"
        in it["sections"][0]["provenance"]
    )
    assert SECRET not in str(out) and "They asked for another example" not in str(out)
    assert it["notes"] == ["What you noticed isn't included: choose “What you noticed” to add it."]
    # Chosen: what was noticed, each marked as it was written.
    chosen = item(reflection_item(client, h, ev["id"], parts=["observations"]), "reflection")
    assert chosen["sections"][0]["text"] == (
        f"- What happened: They asked for another example\n- What you thought it meant: They disliked me {SECRET}"
    )
    # Never edited by putting it in a packet.
    after = client.get(url, headers=h).json()
    assert (after["revision"], after["updated_at"]) == (before["revision"], before["updated_at"])


def test_the_interviewers_come_from_its_kit_only_when_chosen_and_aren_t_repeated_beside_the_kit(client):
    h = nurse(client)
    a, ev = a_kit(client, h)
    url = f"{APPS}/{a['id']}/events/{ev['id']}/reflection"
    reflect(client, h, url)
    alone = item(reflection_item(client, h, ev["id"]), "reflection")
    assert "Dana Synthetic" not in str(alone)
    assert "The interviewers' names aren't included: choose “Interviewers” to add them." in alone["notes"]
    named = item(reflection_item(client, h, ev["id"], parts=["interviewers"]), "reflection")
    assert named["sections"][0]["heading"] == "Interviewers (from the interview's kit)"
    assert named["sections"][0]["text"] == "- Dana Synthetic (Ward manager)"
    # With the kit in the same packet (chosen after it): right after the kit, and not repeated.
    both = packet(
        client,
        h,
        [
            {"type": "reflection", "id": ev["id"], "parts": ["went_well", "interviewers"]},
            {"type": "question", "id": "registered-nurse/m-pressure-0"},
            {"type": "kit", "id": ev["id"], "parts": ["checklist", "interviewers"]},
        ],
    ).json()
    assert [i["type"] for i in both["items"]] == ["question", "kit", "reflection"]
    refl = item(both, "reflection")
    assert refl["notes"] == [
        "This interview's kit is beside this reflection in the packet, so it isn't repeated here.",
        "What you noticed isn't included: choose \u201cWhat you noticed\u201d to add it.",
    ]
    assert str(refl).count("Dana Synthetic") == 0 and str(item(both, "kit")).count("Dana Synthetic") == 1


def test_a_story_deleted_since_is_said_and_a_deleted_or_another_accounts_reflection_is_not_found(client):
    h = nurse(client)
    sid = a_story(client, h)
    kept = a_story(client, h, "Night shift handover")
    a, ev, url = event(client, h)
    reflect(client, h, url, story_ids=[sid, kept])
    assert client.delete(f"/api/v1/me/stories/{sid}", headers=h).status_code == 204
    text = text_of(item(reflection_item(client, h, ev["id"], parts=["stories"]), "reflection"))
    assert text.endswith(
        "- A story you linked was deleted from your story bank since.\n"
        "- Night shift handover (your story, revision 1, read now)\n  I triaged two calls at once."
    )
    other = nurse(client, "other@example.com")
    theirs = packet(client, other, [{"type": "reflection", "id": ev["id"]}]).json()
    assert (
        theirs["items"] == [] and theirs["unavailable"][0]["reason"] == "Not found: it may have been deleted."
    )
    assert SECRET not in str(theirs)
    # A reflection goes with its interview event.
    assert client.delete(f"{APPS}/{a['id']}/events/{ev['id']}", headers=h).status_code == 200
    with client.app.state.session_factory() as db:
        assert db.scalar(select(InterviewReflection).where(InterviewReflection.event_id == ev["id"])) is None
    gone = packet(client, h, [{"type": "reflection", "id": ev["id"]}]).json()
    assert gone["unavailable"][0]["reason"] == "Not found: it may have been deleted."


def test_contact_details_in_a_reflection_are_removed_unless_kept(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    reflect(client, h, url, follow_ups="Email dana.synthetic@example.com or call +1 555 010 2030 on Friday")
    out = reflection_item(client, h, ev["id"], parts=["follow_ups"])
    assert "dana.synthetic@example.com" not in str(out) and out["redacted"] == 2
    kept = reflection_item(client, h, ev["id"], parts=["follow_ups"], keep_contact_details=True)
    assert "dana.synthetic@example.com" in str(kept)


def test_the_list_says_only_whether_each_has_private_details(client):
    h = nurse(client)
    a, ev = a_kit(client, h)
    reflect(client, h, f"{APPS}/{a['id']}/events/{ev['id']}/reflection", follow_ups="Ring 0161 496 0000 back")
    _, ev2, url2 = event(client, h)
    reflect(client, h, url2, observations=[])
    r = client.get(LIST, headers=h)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["total"] == 2 and body["limit"] == 30
    by = {x["event_id"]: x for x in body["items"]}
    assert (
        by[ev["id"]]["has_observations"],
        by[ev["id"]]["has_interviewers"],
        by[ev["id"]]["has_contact_details"],
    ) == (
        True,
        True,
        True,
    )
    assert (
        by[ev2["id"]]["has_observations"],
        by[ev2["id"]]["has_interviewers"],
        by[ev2["id"]]["has_contact_details"],
    ) == (
        False,
        False,
        False,
    )
    assert SECRET not in r.text and "Dana Synthetic" not in r.text and "0161" not in r.text
    assert client.get(LIST, headers=nurse(client, "other@example.com")).json() == {
        "items": [],
        "total": 0,
        "limit": 30,
    }


def test_an_edit_after_a_preview_shows_in_the_next_one(client):
    h = nurse(client)
    a, ev, url = event(client, h)
    first = reflect(client, h, url)
    one = reflection_item(client, h, ev["id"], parts=["went_well"])
    reflect(client, h, url, clear="Explaining my handover routine", expected_revision=first["revision"])
    two = reflection_item(client, h, ev["id"], parts=["went_well"])
    assert "My opening about the ward" in str(one) and "Explaining my handover routine" in str(two)
    assert one["digest"] != two["digest"]


def test_unknown_reflection_parts_are_refused(client):
    h = nurse(client)
    r = client.post(
        PREVIEW, headers=h, json={"items": [{"type": "reflection", "id": "x", "parts": ["meeting_link"]}]}
    )
    assert r.status_code == 422
