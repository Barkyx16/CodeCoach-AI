"""Versioned job requirements (Volume 12, prompt 5; docs/REQUIREMENT_VERSIONS.md): identity through
edits, explicit changes before saving, links that keep their version, nothing equated silently.
Synthetic data only."""

from sqlalchemy import update

from app.models import ExperienceEntry
from tests.test_targets import ANSWER, create, nurse

LICENSE = "Current RN license"


def items(t):
    return [
        {"id": r["id"], "category": r["category"], "text": r["text"], "removed": r["removed"]}
        for r in t["requirement_list"]
    ]


def by_text(t, text):
    return next(r for r in t["requirement_list"] if r["text"] == text)


def by_id(t, rid):
    return next(r for r in t["requirement_list"] if r["id"] == rid)


def preview(client, h, t, its, same_as=()):
    r = client.post(
        f"/api/v1/targets/{t['id']}/requirements/revision/preview",
        headers=h,
        json={"expected_revision": t["requirements_revision"], "items": its, "same_as": list(same_as)},
    )
    assert r.status_code == 200, r.text
    return r.json()


def save(client, h, t, its, same_as=(), revision=None):
    return client.put(
        f"/api/v1/targets/{t['id']}/requirements",
        headers=h,
        json={
            "expected_revision": revision if revision is not None else t["requirements_revision"],
            "items": its,
            "same_as": list(same_as),
        },
    )


def story(client, h, t, rid, title="Night shift escalation"):
    r = client.post(
        f"/api/v1/targets/{t['id']}/experience",
        headers=h,
        json={
            "title": title,
            "situation": "A night shift.",
            "action": "I escalated.",
            "result": "Stable.",
            "requirement_ids": [rid],
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def link(t, rid):
    return next(lk for e in t["experience"] for lk in e["requirement_links"] if lk["requirement_id"] == rid)


def test_a_cosmetic_edit_keeps_the_identity_and_raises_no_review(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    t = story(client, h, t, rid)
    its = items(t)
    next(i for i in its if i["id"] == rid)["text"] = "current  RN license."
    p = preview(client, h, t, its)
    change = next(c for c in p["changes"] if c["requirement_id"] == rid)
    assert change["state"] == "cosmetic" and change["version_from"] == change["version_to"] == 1
    assert p["summary"] == f"0 changed, 0 added, 0 removed, {len(its)} unchanged"
    saved = save(client, h, t, its).json()
    assert by_id(saved, rid)["version"] == 1 and by_id(saved, rid)["text"] == "current  RN license."
    assert link(saved, rid)["status"] == "current"


def test_a_substantive_edit_makes_a_new_version_and_earlier_links_say_so(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    t = story(client, h, t, rid)
    assert link(t, rid)["status"] == "current" and link(t, rid)["linked_version"] == 1
    its = items(t)
    next(i for i in its if i["id"] == rid)["text"] = "Current RN license and BLS certification"
    p = preview(client, h, t, its)
    change = next(c for c in p["changes"] if c["requirement_id"] == rid)
    assert (change["state"], change["version_from"], change["version_to"]) == ("changed", 1, 2)
    assert [s["title"] for s in change["stories"]] == ["Night shift escalation"]
    saved = save(client, h, t, its).json()
    assert by_id(saved, rid)["version"] == 2 and by_id(saved, rid)["id"] == rid
    lk = link(saved, rid)
    assert (
        lk["status"] == "earlier_wording"
        and lk["label"] == "Linked to an earlier wording (version 1; now version 2)"
    )
    history = client.get(f"/api/v1/targets/{t['id']}/requirements/{rid}/history", headers=h).json()
    assert [(x["version"], x["state"], x["text"]) for x in history] == [
        (1, "original", LICENSE),
        (2, "changed", "Current RN license and BLS certification"),
    ]
    # Reusing the story for the current wording is a deliberate, recorded step.
    entry = saved["experience"][0]["id"]
    reused = client.post(
        f"/api/v1/targets/{t['id']}/experience/{entry}/requirements/{rid}/reuse", headers=h
    ).json()
    lk = link(reused, rid)
    assert (
        lk["status"] == "current"
        and lk["reused_from"] == 1
        and lk["label"].startswith("Reused for the current wording")
    )


def test_the_summary_counts_every_kind_of_change(client):
    h = nurse(client)
    t = create(client, h)
    its = items(t)
    live = [i for i in its if not i["removed"]]
    live[0]["text"] = live[0]["text"] + " in a busy unit"
    live[1]["text"] = "Something completely different to do"
    live[2]["removed"] = True
    its.append({"category": "tool", "text": "Uses an electronic health record daily", "removed": False})
    p = preview(client, h, t, its)
    unchanged = len(its) - 1 - 3
    assert p["summary"] == f"2 changed, 1 added, 1 removed, {unchanged} unchanged"
    assert p["counts"] == {"changed": 2, "added": 1, "removed": 1, "restored": 0, "unchanged": unchanged}


def test_a_similar_new_requirement_is_only_a_suggestion_until_accepted(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    t = story(client, h, t, rid)
    its = items(t)
    next(i for i in its if i["id"] == rid)["removed"] = True
    its.append(
        {"category": "required_skill", "text": "Current registered nurse RN license", "removed": False}
    )
    new_index = len(its) - 1
    p = preview(client, h, t, its)
    [s] = p["suggestions"]
    assert (
        s["requirement_id"] == rid
        and s["index"] == new_index
        and "Is it the same requirement?" in s["question"]
    )
    # Declined (not sent back): two separate requirements; the old one is removed, its link kept.
    declined = save(client, h, t, its).json()
    assert by_id(declined, rid)["removed"] is True
    new = by_text(declined, "Current registered nurse RN license")
    assert new["id"] != rid and new["version"] == 1
    assert link(declined, rid)["status"] == "removed"
    history = client.get(f"/api/v1/targets/{t['id']}/requirements/{rid}/history", headers=h).json()
    assert [x["state"] for x in history] == ["original", "removed"]


def test_an_accepted_suggestion_links_the_versions(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    its = items(t)
    next(i for i in its if i["id"] == rid)["removed"] = True
    its.append(
        {"category": "required_skill", "text": "Current registered nurse RN license", "removed": False}
    )
    accepted = save(client, h, t, its, same_as=[{"index": len(its) - 1, "requirement_id": rid}]).json()
    r = by_id(accepted, rid)
    assert (r["removed"], r["version"], r["text"]) == (False, 2, "Current registered nurse RN license")
    assert len(accepted["requirement_list"]) == len(t["requirement_list"])  # no second requirement


def test_two_tabs_saving_at_once_the_stale_one_is_refused_with_the_saved_set(client):
    h = nurse(client)
    t = create(client, h)
    first, second = items(t), items(t)
    first[0]["text"] = first[0]["text"] + " every shift"
    assert save(client, h, t, first).status_code == 200
    second[1]["text"] = "Another substantive wording entirely"
    r = save(client, h, t, second)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"
    current = r.json()["error"]["details"]["current"]
    assert current["requirement_list"][0]["text"].endswith(" every shift")
    assert current["requirements_revision"] == t["requirements_revision"] + 1


def test_a_link_without_version_data_says_version_not_recorded(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    story(client, h, t, rid)
    with client.app.state.session_factory() as db:
        db.execute(update(ExperienceEntry).values(requirement_versions=None))
        db.commit()
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    lk = link(t, rid)
    assert (
        lk["status"] == "not_recorded"
        and lk["label"].endswith("version not recorded")
        and lk["linked_version"] is None
    )


def test_single_edits_are_versioned_too(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    url = f"/api/v1/targets/{t['id']}/requirements/{rid}"
    after = client.patch(url, headers=h, json={"text": "current RN license"}).json()
    assert by_id(after, rid)["version"] == 1  # cosmetic
    after = client.patch(url, headers=h, json={"text": "A current RN license in this state"}).json()
    assert by_id(after, rid)["version"] == 2
    assert after["requirements_revision"] == t["requirements_revision"] + 2
    after = client.patch(url, headers=h, json={"removed": True}).json()
    history = client.get(f"/api/v1/targets/{t['id']}/requirements/{rid}/history", headers=h).json()
    assert [x["state"] for x in history] == ["original", "changed", "removed"]


def test_attempts_keep_the_version_they_were_answered_against(client):
    h = nurse(client)
    t = create(client, h)
    mapped = next(
        r for r in t["requirement_list"] if r["practice"] and r["practice"][0]["kind"] == "question"
    )
    href = mapped["practice"][0]["href"]
    qid = href.rstrip("/").split("/")[-1].split("?")[0]
    assert (
        client.post(
            f"/api/v1/careers/registered-nurse/questions/{qid}/answers", headers=h, json={"answer": ANSWER}
        ).status_code
        == 201
    )
    t = client.get(f"/api/v1/targets/{t['id']}", headers=h).json()
    its = items(t)
    edited = next(i for i in its if i["id"] == mapped["id"])
    edited["text"] = edited["text"] + " for complex patients"
    t = save(client, h, t, its).json()
    attempt = next(a for a in t["recent_attempts"] if mapped["id"] in a["requirement_ids"])
    assert attempt["requirement_versions"][mapped["id"]] == 1  # answered before the edit
    assert by_id(t, mapped["id"])["version"] == 2


def test_an_active_interview_keeps_its_questions(client):
    h = nurse(client)
    t = create(client, h)
    rnd = t["mock_interview"]["round"]
    iv = client.post("/api/v1/interviews", headers=h, json={"kind": "questions", **rnd}).json()
    before = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()
    its = items(t)
    for i in its:
        if not i["removed"]:
            i["removed"] = True
    assert save(client, h, t, its).status_code == 200
    after = client.get(f"/api/v1/interviews/{iv['id']}", headers=h).json()
    asked = [(q["id"], q["title"], q["prompt"]) for q in before["questions"]]
    assert asked and [(q["id"], q["title"], q["prompt"]) for q in after["questions"]] == asked
    assert after["status"] == before["status"]


def test_another_accounts_target_requirements_and_stories_are_refused(client):
    mine = nurse(client)
    theirs = nurse(client, email="grace@example.com")
    t = create(client, theirs)
    rid = by_text(t, LICENSE)["id"]
    t = story(client, theirs, t, rid)
    entry = t["experience"][0]["id"]
    body = {"expected_revision": t["requirements_revision"], "items": items(t), "same_as": []}
    assert (
        client.post(
            f"/api/v1/targets/{t['id']}/requirements/revision/preview", headers=mine, json=body
        ).status_code
        == 404
    )
    assert client.put(f"/api/v1/targets/{t['id']}/requirements", headers=mine, json=body).status_code == 404
    assert (
        client.get(f"/api/v1/targets/{t['id']}/requirements/{rid}/history", headers=mine).status_code == 404
    )
    assert (
        client.post(
            f"/api/v1/targets/{t['id']}/experience/{entry}/requirements/{rid}/reuse", headers=mine
        ).status_code
        == 404
    )
    # Their requirement id inside my own target's set reads as unknown.
    own = create(client, mine)
    its = items(own) + [{"id": rid, "category": "tool", "text": "x x", "removed": False}]
    r = client.post(
        f"/api/v1/targets/{own['id']}/requirements/revision/preview",
        headers=mine,
        json={"expected_revision": own["requirements_revision"], "items": its, "same_as": []},
    )
    assert r.status_code == 404


def by_skill(skill):
    from app.careers.skills import questions_by_skill

    return questions_by_skill("registered-nurse")[skill]


def add_requirement(client, h, t, text, category="required_skill"):
    its = items(t) + [{"category": category, "text": text, "removed": False}]
    r = save(client, h, t, its)
    assert r.status_code == 200, r.text
    return r.json(), by_text(r.json(), text)


def test_an_earlier_attempt_stays_with_the_wording_it_practised_after_a_rewording(client):
    """Rewording a requirement so it maps to other questions doesn't detach what was practised for
    the earlier wording: the attempt keeps its link at the version it was answered against."""
    h = nurse(client)
    t, r = add_requirement(client, h, create(client, h), "Strong patient education every shift")
    assert "patient education" in r["skills"]
    qid = sorted(by_skill("patient education") - by_skill("infection control"))[0]
    assert (
        client.post(
            f"/api/v1/careers/registered-nurse/questions/{qid}/answers", headers=h, json={"answer": ANSWER}
        ).status_code
        == 201
    )
    its = items(client.get(f"/api/v1/targets/{t['id']}", headers=h).json())
    next(i for i in its if i["id"] == r["id"])["text"] = "Strong infection control in every room"
    t = save(client, h, client.get(f"/api/v1/targets/{t['id']}", headers=h).json(), its).json()
    assert by_id(t, r["id"])["version"] == 2 and "patient education" not in by_id(t, r["id"])["skills"]
    attempt = next(a for a in t["recent_attempts"] if a["href"].split("?")[0].endswith(f"/{qid}"))
    assert r["id"] in attempt["requirement_ids"] and attempt["requirement_versions"][r["id"]] == 1


def mappable(skill):
    """A skill a requirement's wording maps to (so the test doesn't depend on the bank's oddities)."""
    from app.services.roles import map_skills

    return skill in map_skills(f"Strong {skill} every shift", "registered-nurse")


def accepted_action_for(client, h, t):
    """An accepted improvement whose retry question a requirement of `t` maps to (one is added).
    Rounds pick questions at random, so it takes the first improvement whose question a
    requirement's wording can map to, starting another round if none can (rare)."""
    from app.careers.skills import questions_by_skill
    from tests.test_actions import accept
    from tests.test_review import STRONG, WEAK, round_with

    by = questions_by_skill("registered-nurse")
    for _ in range(5):
        iv = round_with(client, h, [STRONG, WEAK, WEAK, None, STRONG])
        questions = client.get(f"/api/v1/interviews/{iv}", headers=h).json()["questions"]
        for imp in client.get(f"/api/v1/interviews/{iv}/review", headers=h).json()["improvements"]:
            index = imp["practice"].get("retry_index")
            if index is None:
                continue
            qid = questions[index]["id"]
            skill = next((s for s, ids in by.items() if qid in ids and mappable(s)), None)
            other = next((s for s, ids in by.items() if qid not in ids and mappable(s)), None)
            if skill and other:
                t, r = add_requirement(client, h, t, f"Strong {skill} every shift")
                assert skill in r["skills"]
                action = accept(client, h, iv, imp["key"]).json()
                return client.get(f"/api/v1/targets/{t['id']}", headers=h).json(), r, action, other
    raise AssertionError("no round had an improvement a requirement can map to")


def test_accepted_actions_a_change_affects_are_listed_and_keep_their_version(client):
    h = nurse(client)
    t, r, action, other = accepted_action_for(client, h, create(client, h))
    [lk] = [x for x in t["action_links"] if x["requirement_id"] == r["id"]]
    assert (lk["action_id"], lk["status"], lk["linked_version"]) == (action["id"], "current", 1)
    its = items(t)
    next(i for i in its if i["id"] == r["id"])["text"] = f"Strong {other} on the ward"
    change = next(c for c in preview(client, h, t, its)["changes"] if c["requirement_id"] == r["id"])
    assert change["state"] == "changed" and [a["id"] for a in change["actions"]] == [action["id"]]
    t = save(client, h, t, its).json()
    [lk] = [x for x in t["action_links"] if x["requirement_id"] == r["id"]]
    assert (
        lk["status"] == "earlier_wording"
        and lk["label"] == "Linked to an earlier wording (version 1; now version 2)"
    )
    # Reusing it for the current wording is deliberate and recorded as a reuse.
    reused = client.post(
        f"/api/v1/targets/{t['id']}/actions/{action['id']}/requirements/{r['id']}/reuse", headers=h
    )
    assert reused.status_code == 200, reused.text
    [lk] = [x for x in reused.json()["action_links"] if x["requirement_id"] == r["id"]]
    assert (lk["status"], lk["linked_version"], lk["reused_from"]) == ("current", 2, 1)
    # The action itself is untouched: its title, source and practice are as they were.
    again = client.get(f"/api/v1/me/actions/{action['id']}", headers=h).json()
    assert {k: again[k] for k in ("title", "source", "practice_href")} == {
        k: action[k] for k in ("title", "source", "practice_href")
    }


def test_a_removed_requirement_keeps_its_links_readable_from_history(client):
    h = nurse(client)
    t = create(client, h)
    rid = by_text(t, LICENSE)["id"]
    t = story(client, h, t, rid)
    its = items(t)
    next(i for i in its if i["id"] == rid)["removed"] = True
    t = save(client, h, t, its).json()
    assert by_id(t, rid)["removed"] is True and link(t, rid)["status"] == "removed"
    assert link(t, rid)["label"] == "Linked to a requirement you removed"
    history = client.get(f"/api/v1/targets/{t['id']}/requirements/{rid}/history", headers=h).json()
    assert [(x["state"], x["text"]) for x in history] == [("original", LICENSE), ("removed", LICENSE)]


def test_versions_history_and_links_are_exported(client):
    h = nurse(client)
    t, r, action, other = accepted_action_for(client, h, create(client, h))
    rid = by_text(t, LICENSE)["id"]
    t = story(client, h, t, rid)
    its = items(t)
    next(i for i in its if i["id"] == rid)["text"] = "Current RN license and BLS certification"
    next(i for i in its if i["id"] == r["id"])["text"] = f"Strong {other} on the ward"
    t = save(client, h, t, its).json()
    client.post(f"/api/v1/targets/{t['id']}/actions/{action['id']}/requirements/{r['id']}/reuse", headers=h)
    doc = client.get("/api/v1/me/export", headers=h, params={"version": 2}).json()
    [target] = doc["target_roles"]
    assert target["requirements_revision"] == t["requirements_revision"]
    lic = next(x for x in target["requirements"] if x["id"] == rid)
    assert lic["version"] == 2 and [(x["version"], x["state"]) for x in lic["history"]] == [
        (1, "original"),
        (2, "changed"),
    ]
    [s] = [x for x in doc["stories"] if x["id"] == t["experience"][0]["id"]]
    assert s["requirement_versions"][rid] == {"version": 1, "reused_from": None}
    [a] = [x for x in doc["accepted_actions"] if x["id"] == action["id"]]
    assert a["requirement_reuse"] == {r["id"]: {"version": 2, "reused_from": 1}}


def test_another_accounts_accepted_action_is_refused(client):
    mine = nurse(client)
    theirs = nurse(client, email="grace@example.com")
    t, r, action, _ = accepted_action_for(client, theirs, create(client, theirs))
    # And one of theirs that links straight to a question the same wording maps to.
    from app.careers.skills import questions_by_skill
    from app.models import AcceptedAction, User

    skill = next(sk for sk in r["skills"])
    qid = sorted(questions_by_skill("registered-nurse")[skill])[0]
    with client.app.state.session_factory() as db:
        grace = db.query(User).filter(User.email == "grace@example.com").one()
        direct = AcceptedAction(
            user_id=grace.id,
            source_kind="interview_improvement",
            source_id=action["source"]["interview_id"],
            source_key="point:direct",
            source={"label": "Direct"},
            title="Direct",
            practice_href=f"/careers/registered-nurse/questions/{qid}",
            recurrence="once",
        )
        db.add(direct)
        db.commit()
        direct_id = direct.id
    assert {
        x["action_id"]
        for x in client.get(f"/api/v1/targets/{t['id']}", headers=theirs).json()["action_links"]
    } == {action["id"], direct_id}
    # My own target with the same wording: their actions are neither listed nor reusable there.
    own, mine_r = add_requirement(client, mine, create(client, mine), r["text"])
    assert own["action_links"] == []
    for aid in (action["id"], direct_id):
        for target, rid in ((t["id"], r["id"]), (own["id"], mine_r["id"])):
            url = f"/api/v1/targets/{target}/actions/{aid}/requirements/{rid}/reuse"
            assert client.post(url, headers=mine).status_code == 404


def test_history_goes_with_the_target_and_with_the_account(client):
    from sqlalchemy import func, select

    from app.models import RequirementVersion

    def rows(user_id=None):
        with client.app.state.session_factory() as db:
            q = select(func.count()).select_from(RequirementVersion)
            return db.scalar(q.where(RequirementVersion.user_id == user_id) if user_id else q)

    h = nurse(client)
    t = create(client, h)
    its = items(t)
    next(i for i in its if i["text"] == LICENSE)["text"] = "Current RN license and BLS certification"
    save(client, h, t, its)
    assert rows() == 2  # original and changed
    assert client.delete(f"/api/v1/targets/{t['id']}", headers=h).status_code in (200, 204)
    assert rows() == 0
    t = create(client, h)
    its = items(t)
    its[0]["removed"] = True
    save(client, h, t, its)
    assert rows() == 2
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204 and rows() == 0
