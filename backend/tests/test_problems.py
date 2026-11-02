import json

from app.db.seed import SEED_DIR


def test_library_has_at_least_ten_problems(client):
    body = client.get("/api/v1/problems", params={"page_size": 100}).json()
    assert body["total"] >= 10
    first = body["items"][0]
    assert set(first) == {"slug", "title", "difficulty", "topics", "summary"}
    assert first["slug"] == "find-largest-number"  # curated order


def test_pagination(client):
    p1 = client.get("/api/v1/problems", params={"page": 1, "page_size": 5}).json()
    p2 = client.get("/api/v1/problems", params={"page": 2, "page_size": 5}).json()
    assert len(p1["items"]) == 5 and p1["page"] == 1
    assert {i["slug"] for i in p1["items"]}.isdisjoint({i["slug"] for i in p2["items"]})
    beyond = client.get("/api/v1/problems", params={"page": 99}).json()
    assert beyond["items"] == [] and beyond["total"] == p1["total"]


def test_filters(client):
    medium = client.get("/api/v1/problems", params={"difficulty": "medium"}).json()
    assert medium["total"] >= 1 and all(i["difficulty"] == "medium" for i in medium["items"])
    stacks = client.get("/api/v1/problems", params={"topic": "stacks"}).json()
    slugs = [i["slug"] for i in stacks["items"]]
    assert {"valid-parentheses", "daily-temperatures"} <= set(slugs)
    assert all("stacks" in i["topics"] for i in stacks["items"])
    search = client.get("/api/v1/problems", params={"q": "SUM"}).json()
    assert {"two-sum", "maximum-subarray"} <= {i["slug"] for i in search["items"]}
    assert client.get("/api/v1/problems", params={"difficulty": "impossible"}).status_code == 422


def test_topics(client):
    topics = {t["topic"]: t["count"] for t in client.get("/api/v1/topics").json()}
    assert topics["arrays"] >= 5 and topics["hash-maps"] >= 2


def test_detail_has_workspace_fields(client):
    p = client.get("/api/v1/problems/two-sum").json()
    assert p["title"] == "Two Sum"
    assert "class Solution" in p["starter_code"] and "twoSum(int[] nums, int target)" in p["starter_code"]
    assert p["signature"]["returns"] == "int[]"
    assert len(p["examples"]) >= 2 and p["constraints"]
    assert p["hint_levels"] == 4


def test_hidden_tests_and_hints_never_leak(client):
    """Blueprint API convention: hidden tests must never be in client-facing payloads."""
    for slug in [
        i["slug"] for i in client.get("/api/v1/problems", params={"page_size": 100}).json()["items"]
    ]:
        p = client.get(f"/api/v1/problems/{slug}").json()
        seed = next(json.loads(f.read_text()) for f in SEED_DIR.glob("*.json") if slug in f.name)
        hidden = [t for t in seed["tests"] if t["visibility"] == "hidden"]
        public = [t for t in seed["tests"] if t["visibility"] == "public"]
        assert p["hidden_test_count"] == len(hidden)
        assert len(p["public_tests"]) == len(public)
        assert "hints" not in p and "expected_complexity" not in p
        raw = json.dumps(p)
        for t in hidden:
            # The hidden case's full input object must not appear anywhere in the payload.
            assert json.dumps(t["input"]) not in raw
        for hint in seed["hints"]:
            assert hint not in raw


def test_unknown_problem(client):
    r = client.get("/api/v1/problems/nope")
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "Problem 'nope' not found"


def slugs(client, **params) -> list[str]:
    return [
        i["slug"] for i in client.get("/api/v1/problems", params={"page_size": 200, **params}).json()["items"]
    ]


def test_search_understands_plain_descriptions_and_abbreviations(client):
    assert slugs(client, q="find the biggest number")[0] == "find-largest-number"
    assert slugs(client, q="longest substring without repeats")[0] == "longest-unique-substring"
    assert slugs(client, q="stack brackets") == ["valid-parentheses"]
    dp = slugs(client, q="dp")
    assert "coin-change" in dp and "climbing-stairs" in dp  # 'dp' means dynamic programming
    assert "two-sum" in slugs(client, q="hashmap")


def test_search_ranks_title_matches_first_and_requires_every_word_when_possible(client):
    results = slugs(client, q="sorted array search")
    assert {"search-rotated-array", "binary-search"} <= set(results[:4])
    assert results[0] == "search-rotated-array"  # every word is in its title
    assert slugs(client, q="zzz") == []
    # Too specific to match everything: falls back to problems with most of the words.
    assert "reverse-string" in slugs(client, q="reverse string quantum")


def test_counts_per_difficulty_follow_the_same_filters(client):
    all_counts = client.get("/api/v1/problems/counts").json()
    total = client.get("/api/v1/problems", params={"page_size": 1}).json()["total"]
    assert sum(all_counts.values()) == total
    easy = client.get("/api/v1/problems", params={"difficulty": "easy", "page_size": 1}).json()["total"]
    assert all_counts["easy"] == easy
    searched = client.get("/api/v1/problems/counts", params={"q": "dp"}).json()
    found = slugs(client, q="dp")
    assert sum(searched.values()) == len(found)
    topic = client.get("/api/v1/problems/counts", params={"topic": "stacks"}).json()
    assert sum(topic.values()) == len(slugs(client, topic="stacks"))
