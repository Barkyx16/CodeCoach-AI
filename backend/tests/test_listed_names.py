"""Names a learner listed are kept out of what leaves the app (Volume 15, prompt 7; docs/PRIVACY.md,
"Names you listed"): one function replaces them, whole words in any letter case and possessives, with
"[name]" and counts them; the practice packet, a shared answer and every coach-context preview call
it, each preview says how many, and what's sent is what was previewed. The learner's own copy never
changes; another account's list is never read; an empty list changes nothing; a canary name never
reaches the logs. Synthetic names and data only."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from app.models import ListedName
from app.services.listed_names import replace_names
from tests.test_coach_context import CODE
from tests.test_coach_context_hints import (
    COMPILE_CANARY,
    OUTPUT_CANARY,
    explain,
    explain_preview,
    failed_submission,
    hint,
    hint_preview,
)
from tests.test_coach_context_hints import setup as hint_setup
from tests.test_coach_context_interviewer import preview as message_preview
from tests.test_coach_context_interviewer import say, sent
from tests.test_coach_context_interviewer import setup as interview_setup
from tests.test_packet import note, packet
from tests.test_shares import answer_question, nurse, open_link, share

URL = "/api/v1/me/listed-names"
NAME = "Priya Raman"


def listing(client, h, *names):
    for n in names:
        r = client.post(URL, headers=h, json={"name": n})
        assert r.status_code == 200, r.text
    return client.get(URL, headers=h).json()


# --- the one function -----------------------------------------------------------------------------


def test_whole_words_any_case_possessives_and_spacing_are_replaced_and_counted():
    text = "I asked priya raman, then PRIYA  RAMAN's manager, and Raman alone; Priya Ramanathan didn't come."
    out, n = replace_names(text, [NAME])
    assert out == "I asked [name], then [name]'s manager, and Raman alone; Priya Ramanathan didn't come."
    assert n == 2
    out, n = replace_names("Ann wrote the Annual report with Anne and Ann’s team.", ["Ann"])
    assert out == "[name] wrote the Annual report with Anne and [name]’s team." and n == 2
    # The longest listed name goes first: one replacement, not two.
    assert replace_names("Dr Lee Chen called.", ["Lee", "Dr Lee Chen"]) == ("[name] called.", 1)


def test_an_empty_list_or_text_without_the_names_changes_nothing():
    assert replace_names("Priya was there.", []) == ("Priya was there.", 0)
    assert replace_names("Nobody listed here.", [NAME]) == ("Nobody listed here.", 0)
    assert replace_names("", [NAME]) == ("", 0)
    # A hyphen joins a longer name: listing "Ann" doesn't touch "Ann-Marie" (list it too if it's hers).
    assert replace_names("Ann-Marie and Ann met Mary-Ann.", ["Ann"]) == (
        "Ann-Marie and [name] met Mary-Ann.",
        1,
    )


# --- the list -------------------------------------------------------------------------------------


def test_the_list_is_private_kept_with_the_account_exported_and_deleted_with_it(client):
    a = nurse(client)
    got = listing(client, a, "  Priya   Raman ", "priya raman", "Mr Okafor")
    assert [i["name"] for i in got["items"]] == ["Mr Okafor", "Priya Raman"]  # one row per name, any case
    assert got["placeholder"] == "[name]" and "Only names on this list are found" in got["note"]
    pid = next(i["id"] for i in got["items"] if i["name"] == "Priya Raman")
    r = client.patch(f"{URL}/{pid}", headers=a, json={"name": "Priya R. Raman"})
    assert r.status_code == 200 and "Priya R. Raman" in [i["name"] for i in r.json()["items"]]
    assert client.patch(f"{URL}/{pid}", headers=a, json={"name": "mr okafor"}).status_code == 409
    assert client.post(URL, headers=a, json={"name": "!!!"}).json()["error"]["code"] == "invalid_name"
    b = nurse(client, email="bea@example.com", name="Bea")
    assert client.get(URL, headers=b).json()["items"] == []
    assert client.delete(f"{URL}/{pid}", headers=b).status_code == 404  # another account's: not found
    assert client.patch(f"{URL}/{pid}", headers=b, json={"name": "x"}).status_code == 404
    doc = client.get("/api/v1/me/export", headers=a).json()
    assert sorted(n["name"] for n in doc["listed_names"]) == ["Mr Okafor", "Priya R. Raman"]
    assert client.delete(f"{URL}/{pid}", headers=a).status_code == 204
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=a, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code in (200, 202, 204), r.text
    with client.app.state.session_factory() as db:
        assert db.scalars(select(ListedName)).all() == []


# --- the packet -----------------------------------------------------------------------------------


def test_the_packet_replaces_listed_names_everywhere_and_the_note_itself_keeps_them(client):
    h = nurse(client)
    n = note(
        client, h, title=f"Prep with {NAME}", body=f"{NAME}'s panel asks about triage. Ask priya raman first."
    )
    before = packet(client, h, [{"type": "note", "id": n["id"]}]).json()
    assert before["names_replaced"] == 0
    listing(client, h, NAME)
    got = packet(client, h, [{"type": "note", "id": n["id"]}]).json()
    text = " ".join([got["items"][0]["title"], *(s["text"] for s in got["items"][0]["sections"])])
    assert NAME.lower() not in text.lower() and "[name]'s panel" in text and "Prep with [name]" in text
    assert got["names_replaced"] == 3 and got["digest"] != before["digest"]
    mine = client.get(f"/api/v1/me/notes/{n['id']}", headers=h).json()
    assert mine["title"] == f"Prep with {NAME}" and NAME in mine["body"]  # your own copy is unchanged


def test_an_empty_list_changes_nothing_and_another_accounts_list_is_never_read(client):
    h = nurse(client)
    n = note(client, h, body=f"Ask {NAME} about the rota.")
    first = packet(client, h, [{"type": "note", "id": n["id"]}]).json()
    b = nurse(client, email="bea@example.com", name="Bea")
    listing(client, b, NAME)
    again = packet(client, h, [{"type": "note", "id": n["id"]}]).json()
    assert again["names_replaced"] == 0 and again["digest"] == first["digest"]
    assert NAME in again["items"][0]["sections"][0]["text"]


# --- a shared answer ------------------------------------------------------------------------------


def test_a_share_shows_the_reviewer_what_the_preview_showed_and_keeps_the_list_it_used(client):
    h = nurse(client)
    a = answer_question(
        client,
        h,
        text=(
            f"When {NAME} asked me to cover two bays, I checked both patients first. "
            "I escalated the one short of breath and documented it. Priya Raman's handover was clear."
        ),
    )
    listing(client, h, NAME)
    p = client.post(
        "/api/v1/me/shares/preview", headers=h, json={"answer_id": a["id"], "note": f"For {NAME}"}
    )
    assert p.status_code == 200, p.text
    p = p.json()
    assert (
        p["names"]["replaced"] == 3 and p["names"]["text"] == "3 names you listed were replaced with [name]."
    )
    assert [s["text"] for s in p["source_sentences"]][0].startswith(f"When {NAME} asked")  # your own copy
    shown = " ".join(s["text"] for s in p["view"]["excerpt"]) + p["view"]["note"]
    assert NAME not in shown and "[name]'s handover" in shown
    made = share(client, h, a["id"], note=f"For {NAME}")
    reviewer = open_link(client, made["token"]).json()
    assert (
        reviewer["view"]["excerpt"] == p["view"]["excerpt"] and reviewer["view"]["note"] == p["view"]["note"]
    )
    # Changing the list later changes nothing already shared, and the share says which list it used.
    client.post(URL, headers=h, json={"name": "patients"})
    detail = client.get(f"/api/v1/me/shares/{made['share']['id']}", headers=h).json()
    assert detail["view"]["excerpt"] == p["view"]["excerpt"]
    assert detail["names"]["listed"] == 1 and detail["names"]["text"].startswith("Your list as it was on ")
    assert "Changing the list now doesn't change this share." in detail["names"]["text"]


# --- the coach and the interviewer ----------------------------------------------------------------


def test_a_hint_preview_replaces_listed_names_in_the_code_and_the_coach_reads_exactly_that(client):
    h, rec = hint_setup(client)
    listing(client, h, NAME)
    code = CODE.replace("// my scratch note:", f"// asked {NAME} about this; Priya Raman's tip:")
    p = hint_preview(client, h, code=code).json()
    item = next(i for i in p["items"] if i["key"] == "code")
    assert NAME not in item["text"] and "asked [name] about this; [name]'s tip:" in item["text"]
    assert "2 names you listed were replaced with [name]." in item["notes"]
    assert p["names_replaced"] == 2 and p["names_note"] == "2 names you listed were replaced with [name]."
    r = hint(client, h, p["context_fingerprint"], code=code)
    assert r.status_code == 200, r.text
    [prompt] = rec.prompts
    assert NAME.lower() not in prompt.lower() and "[name]'s tip" in prompt


def test_the_interviewer_reads_the_message_and_the_conversation_with_listed_names_replaced(client):
    h, rec, iv = interview_setup(client)
    first = f"I'd use a hash map, the way {NAME} showed me."
    assert say(client, h, iv, message=first).status_code == 200
    listing(client, h, NAME)
    p = message_preview(client, h, iv, message="As Priya Raman's team does: one pass.").json()
    items = {i["key"]: i for i in p["items"]}
    assert items["message"]["text"] == "As [name]'s team does: one pass."
    assert "1 name you listed was replaced with [name]." in items["message"]["notes"]
    assert (
        NAME not in items["conversation"]["text"]
        and "the way [name] showed me" in items["conversation"]["text"]
    )
    assert p["names_replaced"] == 2
    r = say(client, h, iv, p["context_fingerprint"], message="As Priya Raman's team does: one pass.")
    assert r.status_code == 200, r.text
    prompt = rec.turn_prompts[-1]
    for item in items.values():
        assert sent(item) in prompt, item["key"]
    assert NAME not in prompt
    assert r.json()["turns"][1]["content"] == first  # the transcript keeps what you wrote


def test_a_failure_explanation_replaces_listed_names_in_what_the_program_printed(client):
    h, rec = hint_setup(client)
    sid = failed_submission(client)
    # The synthetic program output and compiler note, listed as (hyphenated) names.
    listing(client, h, OUTPUT_CANARY, COMPILE_CANARY)
    p = explain_preview(client, h, sid).json()
    items = {i["key"]: i for i in p["items"]}
    assert (
        OUTPUT_CANARY not in items["failing_test"]["text"]
        and '"actual": "[name]"' in items["failing_test"]["text"]
    )
    assert (
        COMPILE_CANARY not in items["compile_output"]["text"] and "[name]" in items["compile_output"]["text"]
    )
    assert items["failing_test"]["notes"] == ["1 name you listed was replaced with [name]."]
    assert p["names_replaced"] == 2
    r = explain(client, h, sid, p["context_fingerprint"])
    assert r.status_code == 200, r.text
    assert OUTPUT_CANARY not in rec.prompts[-1] and COMPILE_CANARY not in rec.prompts[-1]


def test_with_no_names_listed_every_preview_reads_as_before(client):
    h, rec = hint_setup(client)
    p = hint_preview(client, h).json()
    assert p["names_replaced"] == 0 and p["names_note"] is None
    assert all(i["names_replaced"] == 0 for i in p["items"])


# --- never in the logs ----------------------------------------------------------------------------


@pytest.mark.parametrize("level", [logging.DEBUG])
def test_a_canary_name_never_reaches_the_logs_or_traces(client, caplog, capsys, level):
    canary = "Zelphine Quorrow"
    caplog.set_level(level)
    h, rec = hint_setup(client)
    listing(client, h, canary)
    n = note(client, h, body=f"{canary} runs the panel.")
    packet(client, h, [{"type": "note", "id": n["id"]}])
    p = hint_preview(client, h, code=CODE.replace("my scratch note", f"{canary} said")).json()
    hint(client, h, p["context_fingerprint"], code=CODE.replace("my scratch note", f"{canary} said"))
    client.get(URL, headers=h)
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    out = capsys.readouterr()
    assert caplog.records  # the access log and traces did run
    assert canary not in logged and canary not in out.out and canary not in out.err
    assert canary.split()[0] not in logged
