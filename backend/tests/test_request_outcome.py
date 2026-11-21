"""What a keyed request made (Volume 8, prompt 1): a reloaded page asks before offering to send
again. The lookup is read-only, searches only the caller's own records, and never takes a key as
permission for anything."""

from tests.conftest import auth_headers, register

CODE = "class Solution { public int[] twoSum(int[] nums, int target) { return new int[0]; } }"
NURSE_ANSWER = (
    "Last winter, on a night shift, I noticed a patient's oxygen had dropped during my assessment. I was "
    "responsible for five patients. I rechecked his vital signs, started oxygen and called the rapid response "
    "team. As a result, he was stable within thirty minutes. I learned to escalate early."
)


def outcome(client, headers, key):
    return client.get(f"/api/v1/me/requests/{key}", headers=headers)


def test_each_kind_of_keyed_request_is_found_with_what_it_made(client, user_headers):
    h = user_headers
    sub = client.post(
        "/api/v1/submissions",
        headers=h,
        json={
            "problem_slug": "two-sum",
            "language": "java",
            "source_code": CODE,
            "client_request_id": "sub-key-0001",
        },
    )
    assert sub.status_code == 202, sub.text
    found = outcome(client, h, "sub-key-0001").json()
    # No judge on this server: saved and queued, so still pending.
    assert found["kind"] == "submission" and found["id"] == sub.json()["id"] and found["state"] == "pending"
    assert found["problem_slug"] == "two-sum"

    run = client.post(
        "/api/v1/submissions",
        headers=h,
        json={
            "problem_slug": "two-sum",
            "language": "java",
            "source_code": CODE,
            "mode": "run",
            "client_request_id": "run-key-0001",
        },
    )
    if run.status_code == 202:  # runs need a judge; refused here (503) means nothing was made
        assert outcome(client, h, "run-key-0001").json()["kind"] == "run"
    else:
        assert outcome(client, h, "run-key-0001").status_code == 404

    hint = client.post(
        "/api/v1/ai/hint",
        headers=h,
        json={
            "problem_slug": "two-sum",
            "level": 1,
            "source_code": CODE,
            "client_request_id": "hint-key-001",
        },
    )
    assert hint.status_code == 200, hint.text
    found = outcome(client, h, "hint-key-001").json()
    assert (found["kind"], found["state"], found["hint_level"], found["problem_slug"]) == (
        "hint",
        "done",
        1,
        "two-sum",
    )

    review = client.post(
        "/api/v1/ai/review",
        headers=h,
        json={"problem_slug": "two-sum", "source_code": CODE, "client_request_id": "review-key-1"},
    )
    assert review.status_code == 200, review.text
    assert outcome(client, h, "review-key-1").json()["kind"] == "review"

    story = client.post(
        "/api/v1/me/stories",
        headers=h,
        json={"title": "Calmed a busy ward", "client_request_id": "story-key-01"},
    )
    assert story.status_code == 201, story.text
    found = outcome(client, h, "story-key-01").json()
    assert (found["kind"], found["id"]) == ("story", story.json()["id"])


def test_an_answer_is_found_too(client):
    h = auth_headers(register(client, email="nurse@example.com", career_track="registered-nurse"))
    r = client.post(
        "/api/v1/careers/registered-nurse/questions/e-time-0/answers",
        headers=h,
        json={"answer": NURSE_ANSWER, "client_request_id": "answer-key-1"},
    )
    assert r.status_code == 201, r.text
    found = outcome(client, h, "answer-key-1").json()
    assert (found["kind"], found["id"]) == ("answer", r.json()["id"])


def test_unknown_keys_and_other_peoples_keys_are_not_found(client, user_headers):
    other = auth_headers(register(client, email="bea@example.com"))
    client.post(
        "/api/v1/me/stories",
        headers=user_headers,
        json={"title": "Mine", "client_request_id": "mine-key-0001"},
    )
    for key, headers in (("never-sent-0001", user_headers), ("mine-key-0001", other)):
        r = outcome(client, headers, key)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "request_not_found"
        assert "never arrived" in r.json()["error"]["message"]


def test_only_well_formed_keys_and_signed_in_callers(client, user_headers):
    assert outcome(client, user_headers, "short").status_code == 422
    assert outcome(client, user_headers, "bad key with spaces!").status_code in (404, 422)
    assert client.get("/api/v1/me/requests/abcdefgh-1234").status_code == 401
