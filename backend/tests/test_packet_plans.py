"""Accepted improvements and one interview's kit in the practice packet (Volume 13, prompt 7;
docs/PACKET.md): read live from the same records as their pages; an improvement is a plan with the
weeks scheduled and marked done, never an achievement; a kit gives its checklist (accepted
improvements read now) and questions to ask, and its meeting link, interviewers and private notes
only when chosen, part by part; one kit per packet; another account's ids are "not found".
Synthetic data only."""

from tests.test_actions import BASE, accept, improvement
from tests.test_kits import event, nurse
from tests.test_packet import packet

SECRET = "CANARY-kit-notes-7f3a9-not-a-real-secret"
LINK = "https://meet.example.com/abc-defg-hij"


def weekly_action(client, h, weeks=3):
    iv, imp = improvement(client, h)
    action = accept(client, h, iv, imp["key"], recurrence="weekly").json()
    made = client.post(
        f"{BASE}/{action['id']}/occurrences", headers=h, json={"on_date": "2026-11-16", "weeks": weeks}
    ).json()
    return action, made["occurrences"]


def a_kit(client, h, action_id=None, **fields):
    a, ev, url = event(client, h)
    checklist = [{"id": "c1", "text": "Bring my ID badge", "origin": "yours", "done": True}]
    if action_id:
        checklist.append({"id": "act-1", "origin": "action", "action_id": action_id, "text": ""})
    body = {
        "checklist": checklist,
        "questions": [
            {"id": "q1", "text": "How is the team's handover done?", "group": "team", "origin": "yours"},
            {
                "id": "q2",
                "text": "Left out of this packet",
                "group": "other",
                "origin": "yours",
                "excluded": True,
            },
        ],
        "meeting_link": LINK,
        "interviewers": [{"name": "Dana Synthetic", "role": "Ward manager"}],
        "notes": f"Parking code {SECRET}",
        **fields,
    }
    r = client.put(url, headers=h, json=body)
    assert r.status_code == 200, r.text
    return a, ev


def item(out, kind):
    return next(i for i in out["items"] if i["type"] == kind)


def text_of(it):
    return "\n".join(f"{s['heading']}\n{s['provenance']}\n{s['text']}" for s in it["sections"])


def test_an_improvement_is_a_plan_with_its_weeks_marked_done_read_live(client):
    h = nurse(client)
    action, occ = weekly_action(client, h)
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h)
    out = packet(client, h, [{"type": "action", "id": action["id"]}])
    assert out.status_code == 200, out.text
    it = item(out.json(), "action")
    assert it["title"] == action["title"]
    [plan, schedule] = it["sections"]
    assert (plan["kind"], plan["heading"]) == ("your_plan", "What you planned")
    assert plan["provenance"].startswith("Accepted improvement, from your practice interview on ")
    assert "weekly, 1 of 3 weeks marked done" in plan["provenance"]
    assert "A plan you made, not a measure of improvement." in plan["provenance"]
    assert schedule["text"].splitlines()[:3] == [
        f"- Week of 2026-11-16: marked done {schedule['text'].split('marked done ')[1].splitlines()[0]}",
        "- Week of 2026-11-23: not marked done",
        "- Week of 2026-11-30: not marked done",
    ]
    # The same as the plan page says.
    page = client.get(f"{BASE}/{action['id']}", headers=h).json()
    assert sum(o["completed_at"] is not None for o in page["occurrences"]) == 1
    # Never an achievement.
    body = text_of(it).lower()
    assert "achiev" not in body and "improved" not in body and "mastered" not in body


def test_a_renamed_improvement_reads_its_new_name_in_a_new_preview(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    before = packet(client, h, [{"type": "action", "id": action["id"]}]).json()
    r = client.patch(
        f"{BASE}/{action['id']}",
        headers=h,
        json={"title": "Say why it matters, every time", "expected_revision": 1},
    )
    assert r.status_code == 200, r.text
    after = packet(client, h, [{"type": "action", "id": action["id"]}]).json()
    assert item(after, "action")["title"] == "Say why it matters, every time"
    assert item(before, "action")["title"] == action["title"] and before["digest"] != after["digest"]


def test_a_kit_gives_its_checklist_and_questions_and_never_its_private_parts_unless_chosen(client):
    h = nurse(client)
    action, occ = weekly_action(client, h, weeks=2)
    client.post(f"{BASE}/{action['id']}/occurrences/{occ[0]['id']}/complete", headers=h)
    _, ev = a_kit(client, h, action_id=action["id"])
    out = packet(client, h, [{"type": "kit", "id": ev["id"]}]).json()
    it = item(out, "kit")
    assert it["title"] == "Kit for Panel interview: Ward nurse at Mercy General"
    assert [s["heading"] for s in it["sections"]] == ["Checklist", "Questions to ask"]
    checklist, questions = it["sections"]
    assert checklist["kind"] == "your_kit"
    assert "[x] Bring my ID badge" in checklist["text"]
    assert f"[ ] {action['title']} (accepted improvement, weekly: 1 of 2 marked done)" in checklist["text"]
    assert questions["text"] == "- How is the team's handover done?"  # the excluded one isn't
    assert checklist["provenance"].startswith(
        "Your interview-day kit for Panel interview (Ward nurse at Mercy General"
    )
    whole = str(out)
    assert LINK not in whole and "Dana Synthetic" not in whole and SECRET not in whole
    assert it["notes"] == [
        "The meeting link isn't included: choose “Meeting link” to add it.",
        "The interviewers' names aren't included: choose “Interviewers” to add them.",
        "Your private kit notes aren't included: choose “Private notes” to add them.",
    ]
    # Chosen part by part.
    chosen = packet(
        client, h, [{"type": "kit", "id": ev["id"], "parts": ["checklist", "meeting_link"]}]
    ).json()
    it = item(chosen, "kit")
    assert [s["heading"] for s in it["sections"]] == ["Checklist", "Meeting link"]
    assert it["sections"][1]["text"] == LINK and SECRET not in str(chosen) and "Dana" not in str(chosen)
    everything = packet(
        client,
        h,
        [
            {
                "type": "kit",
                "id": ev["id"],
                "parts": ["checklist", "questions", "meeting_link", "interviewers", "notes"],
            }
        ],
    ).json()
    assert SECRET in str(everything) and "- Dana Synthetic (Ward manager)" in str(everything)
    assert item(everything, "kit")["notes"] == []


def test_contact_details_in_a_kit_are_removed_by_default(client):
    h = nurse(client)
    _, ev = a_kit(
        client,
        h,
        checklist=[{"id": "c1", "text": "Text dana@example.com the night before", "origin": "yours"}],
        notes="Call 07700 900123 if late",
    )
    out = packet(client, h, [{"type": "kit", "id": ev["id"], "parts": ["checklist", "notes"]}]).json()
    assert "dana@example.com" not in str(out) and "07700 900123" not in str(out)
    assert out["redacted"] == 2
    kept = packet(
        client,
        h,
        [{"type": "kit", "id": ev["id"], "parts": ["checklist", "notes"]}],
        keep_contact_details=True,
    ).json()
    assert "dana@example.com" in str(kept)


def test_one_kit_per_packet_and_a_deleted_or_unsaved_kit_is_said(client):
    h = nurse(client)
    _, first = a_kit(client, h)
    _, second = a_kit(client, h)
    _, unsaved, _ = event(client, h)
    out = packet(
        client,
        h,
        [
            {"type": "kit", "id": first["id"]},
            {"type": "kit", "id": second["id"]},
            {"type": "kit", "id": unsaved["id"]},
            {"type": "kit", "id": "00000000-0000-0000-0000-000000000000"},
        ],
    ).json()
    assert [i["id"] for i in out["items"]] == [first["id"]]
    assert [(u["id"], u["reason"]) for u in out["unavailable"]] == [
        (second["id"], "A packet holds one interview's kit, so this one isn't included."),
        (unsaved["id"], "This interview has no saved kit yet."),
        ("00000000-0000-0000-0000-000000000000", "Not found: it may have been deleted."),
    ]


def test_an_improvement_no_longer_available_is_said_in_the_kit_and_a_deleted_one_is_not_found(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    _, ev = a_kit(client, h, action_id=action["id"])
    with client.app.state.session_factory() as db:
        from app.models import AcceptedAction

        db.delete(db.get(AcceptedAction, action["id"]))
        db.commit()
    out = packet(client, h, [{"type": "kit", "id": ev["id"]}, {"type": "action", "id": action["id"]}]).json()
    assert "[ ] An improvement you removed" in item(out, "kit")["sections"][0]["text"]
    assert out["unavailable"] == [
        {"type": "action", "id": action["id"], "reason": "Not found: it may have been deleted."}
    ]


def test_another_accounts_improvements_and_kits_are_not_found_like_missing_ones(client):
    h = nurse(client)
    action, _ = weekly_action(client, h, weeks=1)
    _, ev = a_kit(client, h, action_id=action["id"])
    other = nurse(client, email="bea@example.com")
    out = packet(
        client, other, [{"type": "action", "id": action["id"]}, {"type": "kit", "id": ev["id"]}]
    ).json()
    assert out["items"] == []
    assert {u["reason"] for u in out["unavailable"]} == {"Not found: it may have been deleted."}
    assert SECRET not in str(out) and action["title"] not in str(out)
    assert client.get("/api/v1/me/packet/kits", headers=other).json() == []


def test_the_kit_list_offers_saved_kits_and_says_what_private_parts_each_has(client):
    h = nurse(client)
    _, ev = a_kit(client, h)
    event(client, h)  # an interview without a saved kit isn't offered
    [k] = client.get("/api/v1/me/packet/kits", headers=h).json()
    assert (
        k["event_id"] == ev["id"]
        and k["event_title"] == "Panel interview"
        and k["employer"] == "Mercy General"
    )
    assert (k["has_meeting_link"], k["has_interviewers"], k["has_notes"]) == (True, True, True)
    assert SECRET not in str(k) and LINK not in str(k)


def test_unknown_parts_for_the_new_sources_are_refused(client):
    h = nurse(client)
    r = packet(client, h, [{"type": "kit", "id": "x", "parts": ["salary"]}])
    assert r.status_code == 422
    r = packet(client, h, [{"type": "action", "id": "x", "parts": ["checklist"]}])
    assert r.status_code == 422
