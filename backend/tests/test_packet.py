"""A private practice packet (Volume 11, prompt 8; docs/PACKET.md): exactly the questions, notes and
stories chosen, in the order chosen, each section labelled with where it came from; your own items
only (another account's id is just not found); unavailable choices said with a reason; contact
details removed by default; bounded; an empty or malformed choice refused rather than exporting
everything; nothing stored. Synthetic accounts only."""

from __future__ import annotations

from app.careers.questions import questions_for
from app.services import packet as pk

from .test_explore import ANSWER, NURSE, nurse

URL = "/api/v1/me/packet/preview"


def note(client, h, **over):
    r = client.post(
        "/api/v1/me/notes", headers=h, json={"title": "Handover notes", "body": "Use SBAR.", **over}
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def story(client, h, **over):
    body = {
        "title": "Two call lights",
        "situation": "A busy night shift.",
        "task": "Decide who to see first.",
        "action": "I checked who was at higher risk.",
        "result": "Both seen within five minutes.",
        **over,
    }
    r = client.post("/api/v1/me/stories", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def packet(client, h, items, **over):
    return client.post(URL, headers=h, json={"items": items, **over})


def test_exactly_what_was_chosen_in_the_order_chosen_each_part_labelled(client):
    h = nurse(client)
    q = questions_for(NURSE)[0]
    answered = client.post(
        f"/api/v1/careers/{NURSE}/questions/{q.id}/answers", headers=h, json={"answer": ANSWER}
    )
    assert answered.status_code == 201, answered.text
    n = note(client, h, reflection="Practise the escalation line.")
    s = story(client, h, reflection="I'd ask for help sooner.")
    items = [
        {"type": "story", "id": s["id"], "parts": ["result", "situation"]},
        {"type": "question", "id": f"{NURSE}/{q.id}", "parts": ["question", "your_answer", "feedback"]},
        {"type": "note", "id": n["id"], "parts": ["note"]},
    ]
    r = packet(client, h, items, title="Week 1 revision")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store", r.text
    body = r.json()
    assert body["title"] == "Week 1 revision" and body["unavailable"] == []
    assert [i["type"] for i in body["items"]] == ["story", "question", "note"]
    # The story's parts in the order asked for, and only those.
    assert [x["heading"] for x in body["items"][0]["sections"]] == ["Result", "Situation"]
    assert "I'd ask for help sooner" not in r.text
    question = body["items"][1]["sections"]
    assert [x["kind"] for x in question] == ["question", "your_answer", "automated_feedback"]
    assert question[0]["text"].startswith(q.prompt) and f"version {q.version}" in question[0]["provenance"]
    assert question[1]["text"] == ANSWER and "Your answer" in question[1]["provenance"]
    assert "Not a grade from a person" in question[2]["provenance"] and "rubric" in question[2]["provenance"]
    assert (
        body["items"][2]["sections"][0]["text"] == "Use SBAR."
        and "revision" in body["items"][2]["sections"][0]["provenance"]
    )
    assert "Practise the escalation line" not in r.text  # the note's reflection wasn't chosen
    # Only what the question's own page shows: never the scoring rubric's internals.
    for point in q.rubric:
        for word in getattr(point, "keywords", ())[:3]:
            assert f'"{word}"' not in r.text
    # The same choice twice: the same content, so the same fingerprint; an edit changes it.
    again = packet(client, h, items, title="Week 1 revision").json()
    assert again["digest"] == body["digest"]
    edited = client.patch(
        f"/api/v1/me/notes/{n['id']}",
        headers=h,
        json={"body": "Use SBAR, always.", "base_revision": n["revision"]},
    )
    assert edited.status_code == 200, edited.text
    assert packet(client, h, items, title="Week 1 revision").json()["digest"] != body["digest"]


def test_unavailable_choices_are_said_not_dropped(client):
    h = nurse(client)
    gone = note(client, h)
    client.delete(f"/api/v1/me/notes/{gone['id']}", headers=h)
    kept = note(client, h, title="Kept")
    q = questions_for(NURSE)[1]
    items = [
        {"type": "note", "id": gone["id"]},
        {"type": "note", "id": kept["id"]},
        {"type": "note", "id": kept["id"]},
        {"type": "question", "id": f"{NURSE}/no-such-question"},
        {"type": "question", "id": "no-such-track/x"},
        {"type": "question", "id": f"{NURSE}/{q.id}", "parts": ["your_answer", "feedback"]},
    ]
    body = packet(client, h, items).json()
    assert [(u["id"], u["reason"]) for u in body["unavailable"]] == [
        (gone["id"], "Not found: it may have been deleted."),
        (kept["id"], "Already in the packet."),
        (f"{NURSE}/no-such-question", "Not in the question library."),
        ("no-such-track/x", "Not in the question library."),
    ]
    assert [i["title"] for i in body["items"]] == ["Kept", q.title]
    assert body["items"][1]["sections"] == []
    assert body["items"][1]["notes"] == [
        "You haven't answered this question, so there's no answer or feedback to include."
    ]


def test_another_accounts_items_are_just_not_found(client):
    ada = nurse(client)
    bea = nurse(client, "bea@example.com")
    adas_note = note(client, ada, body="Ada's private note")
    adas_story = story(client, ada, situation="Ada's private story")
    body = packet(
        client, bea, [{"type": "note", "id": adas_note["id"]}, {"type": "story", "id": adas_story["id"]}]
    ).json()
    assert (
        body["items"] == []
        and [u["reason"] for u in body["unavailable"]] == ["Not found: it may have been deleted."] * 2
    )
    assert "Ada's private" not in str(body)
    assert client.post(URL, json={"items": [{"type": "note", "id": adas_note["id"]}]}).status_code == 401


def test_an_empty_or_malformed_choice_exports_nothing(client):
    h = nurse(client)
    note(client, h, body="Something private")
    for bad in (
        {},
        {"items": []},
        {"items": [{"type": "account", "id": "everything"}]},
        {"items": [{"type": "note", "id": "x", "parts": ["password"]}]},
        {"items": [{"type": "note", "id": f"n{i}"} for i in range(21)]},
    ):
        r = client.post(URL, headers=h, json=bad)
        assert r.status_code == 422, (bad, r.text)
        assert "Something private" not in r.text


def test_contact_details_are_removed_unless_kept_and_text_is_left_as_written(client):
    h = nurse(client)
    tricky = "Call 07700 900123 or mail ada.lee@example.com. <script>alert(1)</script> ![x](https://example.com/x.png) {{employer}}"
    n = note(client, h, body=tricky)
    removed = packet(client, h, [{"type": "note", "id": n["id"]}]).json()
    text = removed["items"][0]["sections"][0]["text"]
    assert "07700" not in text and "ada.lee@example.com" not in text and removed["redacted"] == 2
    assert "[phone number removed]" in text and "[email address removed]" in text
    assert (
        "<script>alert(1)</script>" in text and "https://example.com/x.png" in text and "{{employer}}" in text
    )
    kept = packet(client, h, [{"type": "note", "id": n["id"]}], keep_contact_details=True).json()
    assert kept["items"][0]["sections"][0]["text"] == tricky and kept["redacted"] == 0


def test_the_packet_is_bounded_and_says_where_it_was_cut(client, monkeypatch):
    h = nurse(client)
    long_code = "\n".join(
        f"    int value{i} = compute(value{i - 1}, {i}); // a long line of code" for i in range(250)
    )
    n = note(client, h, body=long_code, excerpt_kind="code")
    other = note(client, h, title="Second", body="x" * 3000)
    monkeypatch.setattr(pk, "MAX_CHARS", 5000)
    body = packet(client, h, [{"type": "note", "id": n["id"]}, {"type": "note", "id": other["id"]}]).json()
    first, second = (i["sections"][0] for i in body["items"])
    assert first["shortened"] and first["text"].endswith(
        "[Shortened here: a packet holds a bounded amount of text.]"
    )
    assert len(first["text"]) < 5200 and body["shortened"] is True
    assert (
        second["text"] == "[Shortened here: a packet holds a bounded amount of text.]"
        or len(second["text"]) < 100
    )


def test_previews_are_rate_limited_per_account(client):
    h = nurse(client)
    n = note(client, h)
    codes = [packet(client, h, [{"type": "note", "id": n["id"]}]).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


def test_a_retired_question_is_said_not_included(client):
    from app.content import state as content_state
    from app.models import ContentStatus

    h = nurse(client)
    q = questions_for(NURSE)[2]
    with client.app.state.session_factory() as db:
        db.add(
            ContentStatus(
                content_type="question", content_id=f"{NURSE}/{q.id}", reason="Synthetic retirement."
            )
        )
        db.commit()
    content_state.invalidate()
    try:
        body = packet(client, h, [{"type": "question", "id": f"{NURSE}/{q.id}"}]).json()
        assert body["items"] == []
        assert body["unavailable"] == [
            {
                "type": "question",
                "id": f"{NURSE}/{q.id}",
                "reason": "Retired from the library, so it isn't included.",
            }
        ]
    finally:
        content_state.invalidate()
