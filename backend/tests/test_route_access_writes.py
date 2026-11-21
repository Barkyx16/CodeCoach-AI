"""The write routes the cross-account walk in test_route_access.py can't call with its seeded ids
(their ids name records it doesn't make), each called here by another account with the owner's real,
linked ids and valid bodies: refused (403/404), nothing of the owner's in the reply, and everything
the owner can read unchanged afterwards. The same calls by the owner pass the owner check, so the
refusals are the owner checks, not bad ids; and a parent of one's own with another account's child id
is refused too. test_route_access.py fails if a write route it can't walk isn't listed here.
Written in the security pass of 2026-11-21 (docs/SECURITY.md). Synthetic accounts only."""

import json

from tests.conftest import auth_headers, register

SECRET = "ADA-PRIVATE-5519"
NURSE = "registered-nurse"
APPS = "/api/v1/me/applications"

SKIPPED_WRITES = {
    ("DELETE", "/api/v1/me/answers/{answer_id}/flags/{flag_id}"),
    ("DELETE", "/api/v1/me/kit-templates/{template_id}"),
    ("DELETE", "/api/v1/me/listed-names/{name_id}"),
    ("DELETE", "/api/v1/me/offer-comparisons/{comparison_id}"),
    ("DELETE", "/api/v1/me/shares/{share_id}"),
    ("DELETE", "/api/v1/me/shares/{share_id}/feedback/{feedback_id}"),
    ("PATCH", "/api/v1/me/actions/{action_id}"),
    ("PATCH", "/api/v1/me/applications/{app_id}/events/{event_id}/reflection/actions/{action_id}"),
    ("PATCH", "/api/v1/me/kit-templates/{template_id}"),
    ("PATCH", "/api/v1/me/listed-names/{name_id}"),
    ("POST", "/api/v1/me/actions/{action_id}/archive"),
    ("POST", "/api/v1/me/actions/{action_id}/complete"),
    ("POST", "/api/v1/me/actions/{action_id}/delete"),
    ("POST", "/api/v1/me/actions/{action_id}/occurrences"),
    ("POST", "/api/v1/me/actions/{action_id}/reopen"),
    ("POST", "/api/v1/me/actions/{action_id}/unarchive"),
    ("POST", "/api/v1/me/actions/{action_id}/occurrences/{entry_id}/complete"),
    ("POST", "/api/v1/me/actions/{action_id}/occurrences/{entry_id}/reopen"),
    ("POST", "/api/v1/me/answers/{answer_id}/flags/{flag_id}/reinstate"),
    ("POST", "/api/v1/me/applications/{app_id}/events/{event_id}/reflection/actions/{action_id}/accept"),
    ("POST", "/api/v1/me/offer-comparisons/{comparison_id}/archive"),
    ("POST", "/api/v1/me/offer-comparisons/{comparison_id}/unarchive"),
    ("PUT", "/api/v1/me/offer-comparisons/{comparison_id}"),
    ("POST", "/api/v1/me/offer-rehearsals/{rehearsal_id}/finish"),
    ("POST", "/api/v1/me/offer-rehearsals/{rehearsal_id}/phase"),
    ("POST", "/api/v1/me/offer-rehearsals/{rehearsal_id}/turns"),
    ("POST", "/api/v1/me/restore/batches/{batch_id}/remove"),
    ("POST", "/api/v1/me/scenario-attempts/{attempt_id}/steps"),
    ("POST", "/api/v1/me/shares/{share_id}/close"),
    ("POST", "/api/v1/me/shares/{share_id}/link"),
    ("POST", "/api/v1/me/shares/{share_id}/reopen"),
    ("POST", "/api/v1/me/shares/{share_id}/revoke"),
    ("POST", "/api/v1/me/stories/{story_id}/revisions/{revision}/restore"),
    ("POST", "/api/v1/problems/{slug}/follow-ups/{to_slug}/dismiss"),
    ("POST", "/api/v1/targets/{target_id}/actions/{action_id}/requirements/{requirement_id}/reuse"),
    ("PUT", "/api/v1/me/shares/{share_id}/feedback/{feedback_id}/useful"),
}


def nurse(client, email):
    return auth_headers(register(client, email=email, display_name=email.split("@")[0], career_track=NURSE))


def ok(r, *_codes):
    assert r.status_code in (200, 201), (r.request.method, r.request.url, r.status_code, r.text[:300])
    return r.json() if r.content else None


def seed(client, h, tag):
    """One of everything the 36 routes name, owned by `h`, linked the way the routes need."""
    from tests.test_offer_comparisons import doc
    from tests.test_reflections import REFLECTION
    from tests.test_requirement_versions import accepted_action_for, create

    ids = {}
    # An answer with a flag.
    a = ok(
        client.post(
            f"/api/v1/careers/{NURSE}/questions/m-pressure-0/answers",
            headers=h,
            json={
                "answer": f"Last winter I was the night nurse ({tag}) for five patients. One of them became "
                "confused. I checked his vital signs and called the rapid response team. As a result he "
                "was stable within 30 minutes."
            },
        ),
        201,
    )
    ids["answer_id"] = a["id"]
    label = a["points"][0]["label"]
    rev = ok(
        client.post(
            f"/api/v1/me/answers/{a['id']}/flags",
            headers=h,
            json={"criterion": label, "kind": "disagree", "note": f"note {tag}"},
        )
    )
    ids["flag_id"] = rev["flags"][0]["id"]
    # A kit template, a listed name, an offer comparison.
    ids["template_id"] = ok(
        client.post(
            "/api/v1/me/kit-templates",
            headers=h,
            json={"name": f"Tpl {tag}", "checklist": [{"text": f"item {tag}"}], "questions": []},
        ),
        201,
    )["id"]
    names = ok(client.post("/api/v1/me/listed-names", headers=h, json={"name": f"Priya{tag[-4:]}"}))
    ids["name_id"] = names["items"][0]["id"]
    oc = ok(client.post("/api/v1/me/offer-comparisons", headers=h, json={"title": f"Offers {tag}"}), 201)
    ids["comparison_id"], ids["comparison_rev"] = oc["id"], oc["revision"]
    ids["doc"] = doc()
    # A share with one piece of feedback.
    sh = ok(
        client.post(
            "/api/v1/me/shares",
            headers=h,
            json={"answer_id": a["id"], "acknowledge_link_access": True, "note": f"note {tag}"},
        ),
        201,
    )
    ids["share_id"], ids["token"] = sh["share"]["id"], sh["token"]
    ok(
        client.post(
            "/api/v1/shared/feedback",
            json={"token": sh["token"], "client_request_id": f"fb-{tag}-0001", "clear": f"clear {tag}"},
        ),
        201,
    )
    ids["feedback_id"] = ok(client.get(f"/api/v1/me/shares/{ids['share_id']}", headers=h))["feedback"][0][
        "id"
    ]
    # A target with a requirement an accepted improvement is linked to (so reuse is a real pair).
    t, r, action, _other = accepted_action_for(client, h, create(client, h))
    ids["target_id"], ids["requirement_id"], ids["action_id"] = t["id"], r["id"], action["id"]
    ids["action_rev"] = action["revision"]
    occ = ok(
        client.post(
            f"/api/v1/me/actions/{action['id']}/occurrences", headers=h, json={"on_date": "2026-12-03"}
        )
    )
    ids["entry_id"] = occ["occurrences"][0]["id"]
    ids["archive_fp"] = ok(client.get(f"/api/v1/me/actions/{action['id']}/archive-preview", headers=h))[
        "fingerprint"
    ]
    ids["delete_fp"] = ok(client.get(f"/api/v1/me/actions/{action['id']}/delete-preview", headers=h))[
        "fingerprint"
    ]
    # A reflection with a suggested next step.
    app = ok(
        client.post(
            APPS,
            headers=h,
            json={"employer": f"Mercy {tag}", "role_title": "Ward nurse", "stage": "interviewing"},
        ),
        201,
    )
    ev = ok(
        client.post(
            f"{APPS}/{app['id']}/events", headers=h, json={"title": f"Panel {tag}", "on_date": "2026-11-12"}
        ),
        201,
    )["events"][0]
    url = f"{APPS}/{app['id']}/events/{ev['id']}/reflection"
    ok(client.put(url, headers=h, json=REFLECTION))
    acts = ok(client.post(f"{url}/suggestions", headers=h))["actions"]
    ids["app_id"], ids["event_id"] = app["id"], ev["id"]
    ids["refl_action_id"] = next(x for x in acts if x["kind"] == "note")["id"]
    # An offer rehearsal, a scenario attempt.
    reh = ok(
        client.post("/api/v1/me/offer-rehearsals", headers=h, json={"case_id": "offer-support-analyst"}), 201
    )
    ids["rehearsal_id"], ids["rehearsal_seq"] = reh["id"], reh["turns"][-1]["seq"]
    att = ok(client.post("/api/v1/me/scenarios/rn-two-patients/attempts", headers=h, json={}))
    ids["attempt_id"], ids["node_id"] = att["id"], att["current"]["id"]
    # A story with two revisions.
    st = ok(
        client.post(
            "/api/v1/me/stories",
            headers=h,
            json={"title": f"Story {tag}", "situation": tag, "task": "t", "action": "a", "result": "r"},
        ),
        201,
    )
    st2 = ok(
        client.patch(
            f"/api/v1/me/stories/{st['id']}",
            headers=h,
            json={"situation": f"{tag} v2", "expected_revision": 1},
        )
    )
    ids["story_id"], ids["story_rev"] = st["id"], st2["revision"]
    # A restore batch (a file with one new note).
    raw = json.dumps({"export_version": 1, "notes": [{"title": f"Restored {tag}", "body": tag}]}).encode()
    b = ok(
        client.post(
            "/api/v1/me/restore",
            headers={**h, "Content-Type": "application/json"},
            params={"categories": ["notes"]},
            content=raw,
        ),
        201,
    )
    ids["batch_id"] = b["id"]
    return ids


def calls(i):
    """(method, template, concrete path, body) for every skipped route, with `i`'s ids."""
    A, R = f"/api/v1/me/actions/{i['action_id']}", f"{APPS}/{i['app_id']}/events/{i['event_id']}/reflection"
    S, OC = f"/api/v1/me/shares/{i['share_id']}", f"/api/v1/me/offer-comparisons/{i['comparison_id']}"
    H = f"/api/v1/me/offer-rehearsals/{i['rehearsal_id']}"
    return [
        # non-destructive first, destructive last (so the owner's positive control can run them in order)
        (
            "PATCH",
            "/api/v1/me/actions/{action_id}",
            A,
            {"title": "Mine now", "expected_revision": i["action_rev"]},
        ),
        ("POST", "/api/v1/me/actions/{action_id}/complete", f"{A}/complete", None),
        ("POST", "/api/v1/me/actions/{action_id}/reopen", f"{A}/reopen", None),
        ("POST", "/api/v1/me/actions/{action_id}/occurrences", f"{A}/occurrences", {"on_date": "2026-12-09"}),
        (
            "POST",
            "/api/v1/me/actions/{action_id}/occurrences/{entry_id}/complete",
            f"{A}/occurrences/{i['entry_id']}/complete",
            None,
        ),
        (
            "POST",
            "/api/v1/me/actions/{action_id}/occurrences/{entry_id}/reopen",
            f"{A}/occurrences/{i['entry_id']}/reopen",
            None,
        ),
        (
            "POST",
            "/api/v1/targets/{target_id}/actions/{action_id}/requirements/{requirement_id}/reuse",
            f"/api/v1/targets/{i['target_id']}/actions/{i['action_id']}/requirements/{i['requirement_id']}/reuse",
            None,
        ),
        (
            "POST",
            "/api/v1/me/actions/{action_id}/archive",
            f"{A}/archive",
            {"expected_fingerprint": i["archive_fp"]},
        ),
        ("POST", "/api/v1/me/actions/{action_id}/unarchive", f"{A}/unarchive", None),
        (
            "PATCH",
            "/api/v1/me/applications/{app_id}/events/{event_id}/reflection/actions/{action_id}",
            f"{R}/actions/{i['refl_action_id']}",
            {"title": "Mine now"},
        ),
        (
            "POST",
            "/api/v1/me/applications/{app_id}/events/{event_id}/reflection/actions/{action_id}/accept",
            f"{R}/actions/{i['refl_action_id']}/accept",
            {"target": "notebook"},
        ),
        (
            "POST",
            "/api/v1/me/answers/{answer_id}/flags/{flag_id}/reinstate",
            f"/api/v1/me/answers/{i['answer_id']}/flags/{i['flag_id']}/reinstate",
            None,
        ),
        (
            "PATCH",
            "/api/v1/me/kit-templates/{template_id}",
            f"/api/v1/me/kit-templates/{i['template_id']}",
            {"name": "Mine now", "expected_revision": 1},
        ),
        (
            "PATCH",
            "/api/v1/me/listed-names/{name_id}",
            f"/api/v1/me/listed-names/{i['name_id']}",
            {"name": "Zed"},
        ),
        (
            "PUT",
            "/api/v1/me/offer-comparisons/{comparison_id}",
            OC,
            {"doc": i["doc"], "expected_revision": i["comparison_rev"]},
        ),
        ("POST", "/api/v1/me/offer-comparisons/{comparison_id}/archive", f"{OC}/archive", None),
        ("POST", "/api/v1/me/offer-comparisons/{comparison_id}/unarchive", f"{OC}/unarchive", None),
        (
            "POST",
            "/api/v1/me/offer-rehearsals/{rehearsal_id}/turns",
            f"{H}/turns",
            {"text": "Can you tell me the base pay?", "source": "typed", "after_seq": i["rehearsal_seq"]},
        ),
        ("POST", "/api/v1/me/offer-rehearsals/{rehearsal_id}/phase", f"{H}/phase", {"from_phase": "clarify"}),
        ("POST", "/api/v1/me/offer-rehearsals/{rehearsal_id}/finish", f"{H}/finish", None),
        (
            "POST",
            "/api/v1/me/scenario-attempts/{attempt_id}/steps",
            f"/api/v1/me/scenario-attempts/{i['attempt_id']}/steps",
            {"node_id": i["node_id"]},
        ),
        (
            "POST",
            "/api/v1/me/stories/{story_id}/revisions/{revision}/restore",
            f"/api/v1/me/stories/{i['story_id']}/revisions/1/restore",
            {"expected_revision": i["story_rev"]},
        ),
        (
            "PUT",
            "/api/v1/me/shares/{share_id}/feedback/{feedback_id}/useful",
            f"{S}/feedback/{i['feedback_id']}/useful",
            {"useful": True},
        ),
        ("POST", "/api/v1/me/shares/{share_id}/close", f"{S}/close", None),
        ("POST", "/api/v1/me/shares/{share_id}/reopen", f"{S}/reopen", None),
        ("POST", "/api/v1/me/shares/{share_id}/link", f"{S}/link", None),
        (
            "POST",
            "/api/v1/problems/{slug}/follow-ups/{to_slug}/dismiss",
            "/api/v1/problems/two-sum/follow-ups/two-sum-sorted/dismiss",
            None,
        ),
        (
            "POST",
            "/api/v1/me/restore/batches/{batch_id}/remove",
            f"/api/v1/me/restore/batches/{i['batch_id']}/remove",
            None,
        ),
        (
            "DELETE",
            "/api/v1/me/shares/{share_id}/feedback/{feedback_id}",
            f"{S}/feedback/{i['feedback_id']}",
            None,
        ),
        ("POST", "/api/v1/me/shares/{share_id}/revoke", f"{S}/revoke", None),
        ("DELETE", "/api/v1/me/shares/{share_id}", S, None),
        (
            "DELETE",
            "/api/v1/me/answers/{answer_id}/flags/{flag_id}",
            f"/api/v1/me/answers/{i['answer_id']}/flags/{i['flag_id']}",
            None,
        ),
        (
            "DELETE",
            "/api/v1/me/kit-templates/{template_id}",
            f"/api/v1/me/kit-templates/{i['template_id']}",
            None,
        ),
        ("DELETE", "/api/v1/me/listed-names/{name_id}", f"/api/v1/me/listed-names/{i['name_id']}", None),
        ("DELETE", "/api/v1/me/offer-comparisons/{comparison_id}", OC, None),
        (
            "POST",
            "/api/v1/me/actions/{action_id}/delete",
            f"{A}/delete",
            {"expected_fingerprint": i["delete_fp"]},
        ),
    ]


def snapshot(client, h, i):
    """What the owner can read of everything the routes touch."""
    out = {}
    for path in (
        f"/api/v1/me/actions/{i['action_id']}",
        f"/api/v1/me/shares/{i['share_id']}",
        f"/api/v1/me/kit-templates/{i['template_id']}",
        "/api/v1/me/listed-names",
        f"/api/v1/me/offer-comparisons/{i['comparison_id']}",
        f"/api/v1/me/offer-rehearsals/{i['rehearsal_id']}",
        f"/api/v1/me/scenario-attempts/{i['attempt_id']}",
        f"/api/v1/me/stories/{i['story_id']}",
        f"/api/v1/me/answers/{i['answer_id']}/review",
        f"{APPS}/{i['app_id']}/events/{i['event_id']}/reflection",
        f"/api/v1/targets/{i['target_id']}",
        "/api/v1/me/restore/batches",
        "/api/v1/me/notes",
    ):
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.status_code)
        out[path] = r.json()
    return out


def test_another_account_is_refused_on_every_skipped_write_route(client):
    ada = nurse(client, "ada@example.com")
    bea = nurse(client, "bea@example.com")
    a = seed(client, ada, SECRET)
    table = calls(a)
    assert {(m, t) for m, t, _, _ in table} == SKIPPED_WRITES and len(SKIPPED_WRITES) == 36
    before = snapshot(client, ada, a)
    for method, template, path, body in table:
        if "follow-ups" in template:
            continue  # public slugs only: Bea's own dismissal (checked separately below)
        r = client.request(method, path, headers=bea, json=body)
        assert r.status_code in (403, 404), (method, template, r.status_code, r.text[:200])
        assert SECRET not in r.text, (method, template)
        for k in ("action_id", "share_id", "answer_id", "story_id", "target_id", "app_id"):
            assert a[k] not in r.text or a[k] in path, (method, template, "leaked id", k)
    after = snapshot(client, ada, a)
    # Rehearsal/attempt/story/etc. unchanged by anything Bea sent (timestamps included).
    assert after == before
    # Follow-up dismissal is per account: Bea's doesn't touch Ada's.
    d0 = client.get("/api/v1/me/dismissals", headers=ada).json()
    client.post("/api/v1/problems/two-sum/follow-ups/two-sum-sorted/dismiss", headers=bea)
    assert client.get("/api/v1/me/dismissals", headers=ada).json() == d0


def test_the_owner_passes_the_owner_check_on_the_same_calls(client):
    """Positive control: with the same ids and bodies the owner gets past the owner check (never
    401/403/404/422), so the other account's 404s above are the owner checks, not bad ids."""
    ada = nurse(client, "ada@example.com")
    a = seed(client, ada, SECRET)
    for method, template, path, body in calls(a):
        r = client.request(method, path, headers=ada, json=body)
        assert r.status_code not in (401, 403, 404, 422) and r.status_code < 500, (
            method,
            template,
            r.status_code,
            r.text[:300],
        )


def test_nested_ids_of_another_account_under_your_own_parent_are_refused(client):
    """The inner id must belong to the outer one: Bea's own parent with Ada's child id."""
    ada = nurse(client, "ada@example.com")
    bea = nurse(client, "bea@example.com")
    a = seed(client, ada, SECRET)
    b = seed(client, bea, "BEA-OWN-0042")
    nested = [
        ("POST", f"/api/v1/me/actions/{b['action_id']}/occurrences/{a['entry_id']}/complete", None),
        ("POST", f"/api/v1/me/actions/{b['action_id']}/occurrences/{a['entry_id']}/reopen", None),
        ("POST", f"/api/v1/me/answers/{b['answer_id']}/flags/{a['flag_id']}/reinstate", None),
        ("DELETE", f"/api/v1/me/answers/{b['answer_id']}/flags/{a['flag_id']}", None),
        ("PUT", f"/api/v1/me/shares/{b['share_id']}/feedback/{a['feedback_id']}/useful", {"useful": True}),
        ("DELETE", f"/api/v1/me/shares/{b['share_id']}/feedback/{a['feedback_id']}", None),
        (
            "PATCH",
            f"{APPS}/{b['app_id']}/events/{b['event_id']}/reflection/actions/{a['refl_action_id']}",
            {"title": "x"},
        ),
        (
            "POST",
            f"{APPS}/{b['app_id']}/events/{b['event_id']}/reflection/actions/{a['refl_action_id']}/accept",
            {"target": "notebook"},
        ),
        # Bea's app with Ada's event (and the reverse).
        (
            "PATCH",
            f"{APPS}/{b['app_id']}/events/{a['event_id']}/reflection/actions/{a['refl_action_id']}",
            {"title": "x"},
        ),
        (
            "PATCH",
            f"{APPS}/{a['app_id']}/events/{b['event_id']}/reflection/actions/{b['refl_action_id']}",
            {"title": "x"},
        ),
        (
            "POST",
            f"/api/v1/targets/{b['target_id']}/actions/{a['action_id']}/requirements/{b['requirement_id']}/reuse",
            None,
        ),
        (
            "POST",
            f"/api/v1/targets/{b['target_id']}/actions/{b['action_id']}/requirements/{a['requirement_id']}/reuse",
            None,
        ),
    ]
    before = snapshot(client, ada, a)
    for method, path, body in nested:
        r = client.request(method, path, headers=bea, json=body)
        assert r.status_code in (403, 404), (method, path, r.status_code, r.text[:200])
        assert SECRET not in r.text, (method, path)
    assert snapshot(client, ada, a) == before
