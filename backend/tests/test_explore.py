"""Practice explorer (search, filters, counts, sorts, pagination), bookmarks and collections."""

from concurrent.futures import ThreadPoolExecutor

from app.careers.questions import questions_for
from app.careers.skills import question_skills
from app.models import Bookmark, CollectionItem, PracticeCollection
from tests.conftest import auth_headers, register

NURSE = "registered-nurse"
ANSWER = (
    "In my last role I owned patient assessment for five patients. I checked vital signs, escalated early "
    "to the charge nurse and documented everything, and as a result the patient was stable within an hour."
)


def nurse(client, email="ada@example.com"):
    return auth_headers(register(client, email=email, career_track=NURSE))


def explore(client, path=f"/api/v1/careers/{NURSE}/explore", headers=None, **params):
    r = client.get(path, headers=headers or {}, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def mine(client, h, **params):
    return explore(client, f"/api/v1/me/explore/{NURSE}", h, **params)


def q(qid):
    return {"item_type": "question", "track": NURSE, "ref_id": qid}


# --- search, filters and counts ----------------------------------------------------------------


def test_the_public_explorer_lists_the_whole_career_with_honest_metadata(client):
    r = explore(client)
    assert r["track"] == NURSE and r["career_title"] == "Registered Nurse"
    assert r["total"] == len(questions_for(NURSE)) == 300
    assert r["page_size"] == 20 and len(r["items"]) == 20
    first = r["items"][0]
    assert first["estimated_minutes"] is None  # the bank doesn't estimate length: never invented
    assert first["skills"] and first["kind"] in {
        "knowledge",
        "behavioral",
        "situational",
        "leadership",
        "motivation",
    }
    assert r["sorts"] == ["library"]  # no "recently added", nothing called personalized
    assert r["explanation"] == [] and r["suggestions"] == []
    assert "status" not in r  # public results never carry personal data


def test_search_matches_titles_skills_and_career_and_ranks_an_exact_title_first(client):
    title = questions_for(NURSE)[5].title
    r = explore(client, q=title)
    assert r["items"][0]["title"] == title
    assert r["sorts"][0] == "relevance"
    assert r["explanation"] == [f"Matching “{title}” in titles, skills, tags and question text"]
    by_skill = explore(client, q="medication administration", page_size=100)
    assert by_skill["total"] > 0
    assert all(
        "medication" in (i["title"] + i["prompt"] + " ".join(i["skills"] + i["tags"])).lower()
        for i in by_skill["items"]
    )
    # The career's own name matches its questions (career scope is explicit, never the account's).
    assert explore(client, q="nurse")["total"] > 0


def test_combined_filters_counts_and_clearing(client):
    all_qs = questions_for(NURSE)
    skill = "patient assessment"
    expected = [
        x
        for x in all_qs
        if x.difficulty == "medium" and x.kind == "knowledge" and skill in question_skills(x)
    ]
    r = explore(client, difficulty="medium", kind="knowledge", skill=skill, page_size=100)
    assert r["total"] == len(expected) and [i["id"] for i in r["items"]] == [x.id for x in expected]
    assert r["explanation"] == ["Difficulty: Medium", "Format: Knowledge", f"Skill: {skill}"]
    # Each facet counts what choosing that option would give, with the *other* filters applied.
    diff = {f["value"]: f["count"] for f in r["facets"]["difficulty"]}
    for level in ("easy", "medium", "hard"):
        assert diff[level] == sum(
            1
            for x in all_qs
            if x.difficulty == level and x.kind == "knowledge" and skill in question_skills(x)
        )
        assert explore(client, difficulty=level, kind="knowledge", skill=skill)["total"] == diff[level]
    kinds = {f["value"]: f["count"] for f in r["facets"]["kind"]}
    assert kinds["knowledge"] == r["total"]
    # Clearing every filter is back to the full career.
    assert explore(client)["total"] == 300


def test_no_results_explains_and_suggests(client):
    r = explore(client, q="zzzz quantum basket weaving", difficulty="hard")
    assert r["total"] == 0 and r["items"] == []
    assert "Try fewer or more general words." in r["suggestions"]
    assert "Remove a filter to widen the results." in r["suggestions"]


def test_pagination_is_deterministic_and_covers_every_result_once(client):
    seen = []
    for page in range(1, 9):
        r = explore(client, difficulty="easy", page=page, page_size=15)
        seen += [i["id"] for i in r["items"]]
    assert len(seen) == len(set(seen)) == 100
    again = [i["id"] for i in explore(client, difficulty="easy", page=3, page_size=15)["items"]]
    assert again == seen[30:45]


def test_bad_filters_and_unknown_careers_are_rejected(client):
    assert client.get(f"/api/v1/careers/{NURSE}/explore", params={"kind": "nope"}).status_code == 422
    assert (
        client.get(f"/api/v1/careers/{NURSE}/explore", params={"sort": "last_practiced"}).status_code == 422
    )
    assert client.get(f"/api/v1/careers/{NURSE}/explore", params={"status": "attempted"}).status_code == 200
    assert client.get("/api/v1/careers/astronaut/explore").status_code == 404
    assert client.get(f"/api/v1/me/explore/{NURSE}").status_code == 401


def test_personal_filters_and_sorts_use_your_own_answers(client):
    h = nurse(client)
    qs = questions_for(NURSE)
    for x in (qs[3], qs[1]):
        r = client.post(
            f"/api/v1/careers/{NURSE}/questions/{x.id}/answers", headers=h, json={"answer": ANSWER}
        )
        assert r.status_code in (200, 201), r.text
    r = mine(client, h, status="attempted")
    assert {i["id"] for i in r["items"]} == {qs[3].id, qs[1].id}
    assert r["explanation"] == ["Questions you've answered"]
    assert r["status"][qs[1].id]["attempts"] == 1 and r["status"][qs[1].id]["best_score"] is not None
    assert mine(client, h, status="unattempted")["total"] == 298
    recent = mine(client, h, sort="last_practiced", page_size=3)
    assert [i["id"] for i in recent["items"][:2]] == [qs[1].id, qs[3].id]
    assert recent["sorts"] == ["library", "last_practiced", "lowest_score"]
    # The public explorer ignores the token: nothing personal leaks into it.
    public = explore(client, headers=h)
    assert "status" not in public and public["sorts"] == ["library"]


# --- bookmarks ---------------------------------------------------------------------------------


def test_bookmarks_are_idempotent_filterable_and_removable(client):
    h = nurse(client)
    qid = questions_for(NURSE)[7].id
    for _ in range(2):
        r = client.put("/api/v1/me/bookmarks", headers=h, json=q(qid))
        assert r.status_code == 200
    marks = r.json()
    assert len(marks) == 1 and marks[0]["ref_id"] == qid and marks[0]["available"]
    assert marks[0]["href"] == f"/careers/{NURSE}/questions/{qid}"
    r = mine(client, h, status="bookmarked")
    assert [i["id"] for i in r["items"]] == [qid] and r["status"][qid]["bookmarked"]
    problem = client.put(
        "/api/v1/me/bookmarks", headers=h, json={"item_type": "problem", "ref_id": "two-sum"}
    )
    assert [b["item_type"] for b in problem.json()] == ["problem", "question"]
    gone = client.delete(
        "/api/v1/me/bookmarks", headers=h, params={"item_type": "question", "track": NURSE, "ref_id": qid}
    )
    assert gone.status_code == 200 and [b["ref_id"] for b in gone.json()] == ["two-sum"]
    again = client.delete(
        "/api/v1/me/bookmarks", headers=h, params={"item_type": "question", "track": NURSE, "ref_id": qid}
    )
    assert again.status_code == 200
    assert client.put("/api/v1/me/bookmarks", headers=h, json=q("no-such-question")).status_code == 404


def test_concurrent_bookmarks_of_the_same_item_keep_one(client):
    h = nurse(client)
    qid = questions_for(NURSE)[2].id
    with ThreadPoolExecutor(4) as pool:
        codes = list(
            pool.map(
                lambda _: client.put("/api/v1/me/bookmarks", headers=h, json=q(qid)).status_code, range(4)
            )
        )
    assert codes == [200] * 4
    assert len(client.get("/api/v1/me/bookmarks", headers=h).json()) == 1


# --- collections -------------------------------------------------------------------------------


def make(client, h, name="Night shift prep"):
    r = client.post("/api/v1/me/collections", headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def add(client, h, cid, item):
    return client.post(f"/api/v1/me/collections/{cid}/items", headers=h, json=item)


def test_collections_create_rename_add_reorder_and_delete(client):
    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    assert c["items"] == 0 and c["item_list"] == [] and not c["queue_started"]
    for x in qs[:3]:
        assert add(client, h, c["id"], q(x.id)).status_code == 200
    c = add(client, h, c["id"], {"item_type": "problem", "ref_id": "two-sum"}).json()
    assert [i["ref_id"] for i in c["item_list"]] == [qs[0].id, qs[1].id, qs[2].id, "two-sum"]
    assert c["item_list"][3]["href"] == "/problems/two-sum" and c["item_list"][3]["title"] == "Two Sum"
    dup = add(client, h, c["id"], q(qs[1].id))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_in_collection"
    renamed = client.patch(f"/api/v1/me/collections/{c['id']}", headers=h, json={"name": "Week 1"}).json()
    assert renamed["name"] == "Week 1"
    ids = [i["id"] for i in c["item_list"]]
    new_order = [ids[3], ids[0], ids[2], ids[1]]
    r = client.put(f"/api/v1/me/collections/{c['id']}/order", headers=h, json={"item_ids": new_order})
    assert [i["id"] for i in r.json()["item_list"]] == new_order
    # The order persists across requests.
    fresh = client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()
    assert [i["id"] for i in fresh["item_list"]] == new_order and [
        i["position"] for i in fresh["item_list"]
    ] == [0, 1, 2, 3]
    bad = client.put(f"/api/v1/me/collections/{c['id']}/order", headers=h, json={"item_ids": new_order[:3]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_order"
    dupe_order = client.put(
        f"/api/v1/me/collections/{c['id']}/order", headers=h, json={"item_ids": [ids[0]] * 4}
    )
    assert dupe_order.status_code == 400
    assert client.delete(f"/api/v1/me/collections/{c['id']}", headers=h).status_code == 204
    assert client.get(f"/api/v1/me/collections/{c['id']}", headers=h).status_code == 404
    assert client.get("/api/v1/me/collections", headers=h).json() == []
    # Deleting a collection never touches bookmarks or the questions themselves.
    assert explore(client)["total"] == 300


def test_one_question_can_live_in_several_collections(client):
    h = nurse(client)
    qid = questions_for(NURSE)[0].id
    a, b = make(client, h, "A"), make(client, h, "B")
    assert add(client, h, a["id"], q(qid)).status_code == 200
    assert add(client, h, b["id"], q(qid)).status_code == 200
    st = mine(client, h, page_size=1)["status"][qid]
    assert sorted(st["collection_ids"]) == sorted([a["id"], b["id"]])
    names = [c["name"] for c in client.get("/api/v1/me/collections", headers=h).json()]
    assert sorted(names) == ["A", "B"]


def test_concurrent_additions_keep_one_copy(client):
    h = nurse(client)
    c = make(client, h)
    qid = questions_for(NURSE)[4].id
    with ThreadPoolExecutor(4) as pool:
        codes = sorted(pool.map(lambda _: add(client, h, c["id"], q(qid)).status_code, range(4)))
    assert codes.count(200) == 1 and set(codes) <= {200, 409}
    assert client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()["items"] == 1


def test_the_practice_queue_tracks_position_and_done_marks_separately_from_mastery(client):
    h = nurse(client)
    qs = questions_for(NURSE)
    c = make(client, h)
    empty = client.put(f"/api/v1/me/collections/{c['id']}/queue", headers=h, json={"position": 0})
    assert empty.status_code == 409 and empty.json()["error"]["code"] == "empty_collection"
    for x in qs[:3]:
        c = add(client, h, c["id"], q(x.id)).json()
    started = client.put(f"/api/v1/me/collections/{c['id']}/queue", headers=h, json={"position": 0}).json()
    assert started["queue_started"] and started["queue_position"] == 0
    first = started["item_list"][0]
    assert not first["practiced_since_added"] and not first["queue_done"]
    client.post(f"/api/v1/careers/{NURSE}/questions/{qs[0].id}/answers", headers=h, json={"answer": ANSWER})
    after = client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()
    assert after["item_list"][0]["practiced_since_added"] and not after["item_list"][0]["queue_done"]
    done = client.put(
        f"/api/v1/me/collections/{c['id']}/items/{first['id']}/done", headers=h, json={"done": True}
    ).json()
    assert done["queue_done"] == 1 and done["item_list"][0]["queue_done"]
    moved = client.put(f"/api/v1/me/collections/{c['id']}/queue", headers=h, json={"position": 99}).json()
    assert moved["queue_position"] == 2  # clamped to the last item
    # Removing an item before the queue position keeps you on the same question.
    removed = client.delete(f"/api/v1/me/collections/{c['id']}/items/{first['id']}", headers=h).json()
    assert removed["queue_position"] == 1 and removed["item_list"][1]["ref_id"] == qs[2].id


def test_a_retired_question_is_shown_as_unavailable_never_swapped(client):
    h = nurse(client)
    c = make(client, h)
    qid = questions_for(NURSE)[0].id
    c = add(client, h, c["id"], q(qid)).json()
    client.put("/api/v1/me/bookmarks", headers=h, json=q(qid))
    # Simulate the question leaving the library: point the saved rows at an id the bank no longer has.
    db = client.app.state.session_factory()
    db.query(CollectionItem).update({"ref_id": "retired-question"})
    db.query(Bookmark).update({"ref_id": "retired-question"})
    db.commit()
    db.close()
    got = client.get(f"/api/v1/me/collections/{c['id']}", headers=h).json()
    item = got["item_list"][0]
    assert not item["available"] and item["href"] is None and item["ref_id"] == "retired-question"
    assert "retired or removed" in item["unavailable_reason"]
    marks = client.get("/api/v1/me/bookmarks", headers=h).json()
    assert not marks[0]["available"] and marks[0]["ref_id"] == "retired-question"
    # It can still be removed, and adding a retired id is refused.
    after = client.delete(f"/api/v1/me/collections/{c['id']}/items/{item['id']}", headers=h).json()
    assert after["item_list"] == []
    assert add(client, h, c["id"], q("retired-question")).status_code == 404
    gone = client.delete(
        "/api/v1/me/bookmarks",
        headers=h,
        params={"item_type": "question", "track": NURSE, "ref_id": "retired-question"},
    )
    assert gone.json() == []


def test_two_accounts_never_see_or_change_each_others_collections(client):
    ada = nurse(client, "ada@example.com")
    bob = nurse(client, "bob@example.com")
    c = make(client, ada, "Ada's private list")
    qid = questions_for(NURSE)[0].id
    add(client, ada, c["id"], q(qid))
    client.put("/api/v1/me/bookmarks", headers=ada, json=q(qid))
    cid, item_id = (
        c["id"],
        client.get(f"/api/v1/me/collections/{c['id']}", headers=ada).json()["item_list"][0]["id"],
    )
    assert client.get("/api/v1/me/collections", headers=bob).json() == []
    assert client.get("/api/v1/me/bookmarks", headers=bob).json() == []
    for method, path, body in [
        ("get", f"/api/v1/me/collections/{cid}", None),
        ("patch", f"/api/v1/me/collections/{cid}", {"name": "mine now"}),
        ("post", f"/api/v1/me/collections/{cid}/items", q(questions_for(NURSE)[1].id)),
        ("delete", f"/api/v1/me/collections/{cid}/items/{item_id}", None),
        ("put", f"/api/v1/me/collections/{cid}/order", {"item_ids": [item_id]}),
        ("put", f"/api/v1/me/collections/{cid}/queue", {"position": 0}),
        ("put", f"/api/v1/me/collections/{cid}/items/{item_id}/done", {"done": True}),
        ("delete", f"/api/v1/me/collections/{cid}", None),
    ]:
        kwargs = {"headers": bob} | ({"json": body} if body is not None else {})
        assert getattr(client, method)(path, **kwargs).status_code == 404, (method, path)
    st = mine(client, bob, page_size=1)
    assert st["status"] == {} and mine(client, bob, status="bookmarked")["total"] == 0
    still = client.get(f"/api/v1/me/collections/{cid}", headers=ada).json()
    assert still["name"] == "Ada's private list" and still["items"] == 1 and not still["queue_started"]


def test_export_includes_bookmarks_and_collections_and_deleting_the_account_removes_them(client):
    h = nurse(client)
    qid = questions_for(NURSE)[0].id
    c = make(client, h)
    add(client, h, c["id"], q(qid))
    client.put("/api/v1/me/bookmarks", headers=h, json=q(qid))
    data = client.get("/api/v1/me/export", headers=h).json()
    assert data["bookmarks"] == [
        {"type": "question", "career": NURSE, "item": qid, "created_at": data["bookmarks"][0]["created_at"]}
    ]
    assert data["collections"][0]["name"] == "Night shift prep"
    assert data["collections"][0]["items"][0]["item"] == qid
    r = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert r.status_code in (200, 204), r.text
    db = client.app.state.session_factory()
    assert db.query(Bookmark).count() == 0 and db.query(PracticeCollection).count() == 0
    assert db.query(CollectionItem).count() == 0
    db.close()


def test_collection_names_are_validated_and_bounded(client):
    h = nurse(client)
    assert client.post("/api/v1/me/collections", headers=h, json={"name": ""}).status_code == 422
    assert client.post("/api/v1/me/collections", headers=h, json={"name": "x" * 81}).status_code == 422
    assert make(client, h, "   ")["name"] == "Untitled"


def test_collections_report_which_ones_already_hold_an_item(client):
    h = nurse(client)
    qid = questions_for(NURSE)[0].id
    a, b = make(client, h, "A"), make(client, h, "B")
    add(client, h, a["id"], q(qid))
    plain = client.get("/api/v1/me/collections", headers=h).json()
    assert all(c["contains"] is None for c in plain)
    asked = client.get("/api/v1/me/collections", headers=h, params=q(qid)).json()
    assert {c["name"]: c["contains"] for c in asked} == {"A": True, "B": False}
    problem = client.get(
        "/api/v1/me/collections", headers=h, params={"item_type": "problem", "ref_id": "two-sum"}
    ).json()
    assert [c["contains"] for c in problem] == [False, False]
    assert b["id"]
