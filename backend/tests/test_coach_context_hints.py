"""What the coach reads for hints and failure explanations (Volume 13, prompt 2; docs/COACH_CONTEXT.md):
each previews its private context exactly, and the request that's sent is bound to what was approved,
the way the code review already is.

A recording provider (the real Claude adapter over a fake client) captures every request, so the checks
compare what was previewed with what a provider actually received, byte for byte. Synthetic data only."""

from types import SimpleNamespace

from sqlalchemy import func, select

from app.models import (
    AIInteraction,
    ExecutionResult,
    Problem,
    Submission,
    SubmissionMode,
    SubmissionStatus,
    TestVisibility,
    User,
)
from app.schemas.ai import FailureExplanation, HintContent
from app.services.ai.anthropic_provider import AnthropicCoach, _numbered
from app.services.ai.context_text import analysis_text, failing_test_text
from tests.conftest import auth_headers, register
from tests.test_ai_coach import FakeMessages
from tests.test_coach_context import CODE, SECRET, used

HINT_PREVIEW = "/api/v1/ai/hint/preview"
HINT = "/api/v1/ai/hint"
EXPLAIN_PREVIEW = "/api/v1/ai/explain-failure/preview"
EXPLAIN = "/api/v1/ai/explain-failure"
# Synthetic canaries: what the learner's program printed, the compiler said, and a hidden test's input
# smuggled into the public results by a (pretend) runner bug.
OUTPUT_CANARY = "CANARY-program-output-41"
COMPILE_CANARY = "CANARY-compiler-note-17"
HIDDEN_CANARY = "CANARY-hidden-input-99"


class Recording:
    """The Claude adapter over a fake client: records each hint and explanation context and prompt."""

    name, model = "anthropic", "m"

    def __init__(self):
        self.hint_messages = FakeMessages(
            parsed=HintContent(
                hint="Think about what you've already seen.", focus_area="lookup", encouragement="Close."
            )
        )
        self.explain_messages = FakeMessages(
            parsed=FailureExplanation(
                cause="wrong-answer",
                headline="The pair search returns the wrong indices.",
                explanation="The loop compares the wrong elements for the failing test.",
                evidence="The first failing public test returned a different pair.",
                line_hint=None,
                next_steps=["Trace the loop on the failing input."],
                concept=None,
                confidence="medium",
            )
        )
        self._hint = AnthropicCoach(
            api_key=None, model="m", client=SimpleNamespace(messages=self.hint_messages)
        )
        self._explain = AnthropicCoach(
            api_key=None, model="m", client=SimpleNamespace(messages=self.explain_messages)
        )
        self.hints: list = []
        self.explanations: list = []

    def hint(self, ctx):
        self.hints.append(ctx)
        return self._hint.hint(ctx)

    def explain_failure(self, ctx):
        self.explanations.append(ctx)
        return self._explain.explain_failure(ctx)

    def __getattr__(self, name):
        raise AssertionError(f"unexpected provider call: {name}")

    @property
    def prompts(self) -> list[str]:
        calls = [*self.hint_messages.calls, *self.explain_messages.calls]
        return [c["messages"][0]["content"] for c in calls]


def setup(client, email="ada@example.com"):
    h = auth_headers(register(client, email=email))
    rec = Recording()
    client.app.state.ai_provider = rec
    return h, rec


def hint_preview(client, h, level=1, code=CODE):
    return client.post(
        HINT_PREVIEW, headers=h, json={"problem_slug": "two-sum", "source_code": code, "level": level}
    )


def hint(client, h, approved, level=1, code=CODE, key=None):
    body = {"problem_slug": "two-sum", "source_code": code, "level": level, "approved_context": approved}
    if key:
        body["client_request_id"] = key
    return client.post(HINT, headers=h, json=body)


def failed_submission(client, email="ada@example.com", leak_hidden=False) -> str:
    """A judged, failed submission: public test 1 passed, public test 2 failed with the program's
    output, compiler warnings kept. `leak_hidden` puts a hidden test's row first in the stored public
    results, as a runner bug would."""
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        problem = db.scalar(select(Problem).where(Problem.slug == "two-sum"))
        public = sum(t.visibility == TestVisibility.PUBLIC for t in problem.test_cases)
        sub = Submission(
            user_id=user.id,
            problem_id=problem.id,
            source_code=CODE,
            status=SubmissionStatus.FAILED,
            mode=SubmissionMode.SUBMIT,
        )
        db.add(sub)
        db.flush()
        rows = [
            {"index": 0, "passed": True, "input": {"nums": [2, 7], "target": 9}, "expected_output": [0, 1]},
            {
                "index": 1,
                "passed": False,
                "input": {"nums": [3, 2, 4], "target": 6},
                "expected_output": [1, 2],
                "actual_output": OUTPUT_CANARY,
            },
        ]
        if leak_hidden:
            rows.insert(0, {"index": public, "passed": False, "input": {"secret": HIDDEN_CANARY}})
        db.add(
            ExecutionResult(
                submission_id=sub.id,
                passed_count=1,
                total_count=len(problem.test_cases),
                public_results=rows,
                stderr_excerpt=f"Solution.java:4: warning: [{COMPILE_CANARY}]",
            )
        )
        db.commit()
        return sub.id


def explain_preview(client, h, sid, compile_output=True, failing_test=True):
    return client.post(
        EXPLAIN_PREVIEW,
        headers=h,
        json={
            "submission_id": sid,
            "share_compile_output": compile_output,
            "share_failing_test": failing_test,
        },
    )


def explain(client, h, sid, approved, compile_output=True, failing_test=True):
    return client.post(
        EXPLAIN,
        headers=h,
        json={
            "submission_id": sid,
            "share_compile_output": compile_output,
            "share_failing_test": failing_test,
            "approved_context": approved,
        },
    )


def interactions(client) -> int:
    with client.app.state.session_factory() as db:
        return db.scalar(select(func.count()).select_from(AIInteraction))


# --- hints ----------------------------------------------------------------------------------------


def test_a_hint_preview_is_exactly_what_the_coach_reads(client):
    h, rec = setup(client)
    p = hint_preview(client, h).json()
    assert p["operation"] == "hint"
    items = {i["key"]: i for i in p["items"]}
    assert list(items) == ["level", "code", "checks"]
    assert items["level"]["text"] == "Requested hint level: 1 (nudge)." and items["level"]["required"]
    code, checks = items["code"], items["checks"]
    assert SECRET not in code["text"] and '"[REDACTED]"' in code["text"]
    assert code["notes"] == ["1 secret-looking string replaced with [REDACTED]."]
    assert checks["derived"] and checks["required"] and not code["derived"]
    assert p["left_out"] == []
    assert p["about"] == [
        "Level 1 of 4: Nudge.",
        "Your first hint for this problem.",
        "Which levels you've seen isn't sent; the level you ask for is.",
    ]
    # The reference hint is public and listed as such, but not shown: checking doesn't give it away.
    with client.app.state.session_factory() as db:
        reference = db.scalar(select(Problem).where(Problem.slug == "two-sum")).hints[0]
    assert "reference hint for level 1" in p["required_public"][1]
    shown = [
        *p["required_public"],
        *p["about"],
        *(i["text"] for i in p["items"]),
        *(n for i in p["items"] for n in i["notes"]),
    ]
    assert all(reference not in line for line in shown)

    r = hint(client, h, p["context_fingerprint"])
    assert r.status_code == 200, r.text
    [ctx] = rec.hints
    assert ctx.code == code["text"] and analysis_text(ctx.analysis) == checks["text"] and ctx.level == 1
    [prompt] = rec.prompts
    assert f"<learner_code>\n{_numbered(code['text'])}\n</learner_code>" in prompt
    assert f"<analysis>\n{checks['text']}\n</analysis>" in prompt
    assert items["level"]["text"] in prompt
    assert SECRET not in prompt


def test_code_edited_after_a_hint_preview_is_refused_with_the_new_code_shown(client):
    h, rec = setup(client)
    p = hint_preview(client, h).json()
    before = used(client, h)
    edited = CODE.replace("return new int[0];", "return null; // edited after the preview")
    r = hint(client, h, p["context_fingerprint"], code=edited)
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    fresh = r.json()["error"]["details"]["preview"]
    assert "edited after the preview" in next(i["text"] for i in fresh["items"] if i["key"] == "code")
    assert rec.hints == [] and used(client, h) == before and interactions(client) == 0
    ok = hint(client, h, fresh["context_fingerprint"], code=edited)
    assert ok.status_code == 200 and "edited after the preview" in rec.hints[0].code


def test_a_hint_resent_after_a_lost_reply_reuses_the_approval_and_never_widens_it(client):
    h, rec = setup(client)
    p = hint_preview(client, h).json()
    first = hint(client, h, p["context_fingerprint"], key="hint-key-0001")
    again = hint(client, h, p["context_fingerprint"], key="hint-key-0001")
    assert again.status_code == 200 and again.json()["content"] == first.json()["content"]
    assert len(rec.prompts) == 1
    # The same key can't later carry other material, even with an approval of its own.
    other = CODE.replace("return new int[0];", "return new int[] {-1, -1};")
    q = hint_preview(client, h, code=other).json()
    reused = hint(client, h, q["context_fingerprint"], code=other, key="hint-key-0001")
    assert reused.status_code == 409 and reused.json()["error"]["code"] == "idempotency_key_reused"
    assert len(rec.prompts) == 1


def test_the_hint_ladder_levels_limits_and_budget_are_unchanged(client):
    h, rec = setup(client)
    locked = hint_preview(client, h, level=2)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "hint_locked"
    assert hint_preview(client, h, level=5).status_code == 422  # not a level at all
    before = used(client, h)
    p1 = hint_preview(client, h, level=1).json()
    assert hint(client, h, p1["context_fingerprint"], level=1).status_code == 200
    assert used(client, h) == before + 1  # one hint, one request; the preview cost nothing
    p2 = hint_preview(client, h, level=2).json()
    assert p2["about"][1] == "You've seen level 1 (Nudge) for this problem, so this one goes further."
    assert hint(client, h, p2["context_fingerprint"], level=2).status_code == 200
    p1_again = hint_preview(client, h, level=1).json()
    assert p1_again["about"][1] == "You've had level 1 before: this asks for it again, about your code now."
    # Without a preview (an older page), a hint is asked for as before.
    old = client.post(HINT, headers=h, json={"problem_slug": "two-sum", "source_code": CODE, "level": 3})
    assert old.status_code == 200 and [c.level for c in rec.hints] == [1, 2, 3]


def test_previewing_twenty_times_spends_nothing_and_calls_no_provider(client):
    h, rec = setup(client)
    sid = failed_submission(client)
    before = used(client, h)
    for _ in range(10):
        assert hint_preview(client, h).status_code == 200
        assert explain_preview(client, h, sid).status_code == 200
    assert rec.hints == [] and rec.explanations == [] and rec.prompts == []
    assert used(client, h) == before and interactions(client) == 0


# --- failure explanations -------------------------------------------------------------------------


def test_an_explanation_preview_is_exactly_what_the_coach_reads(client):
    h, rec = setup(client)
    sid = failed_submission(client)
    p = explain_preview(client, h, sid).json()
    assert p["operation"] == "failure_explanation" and p["already_answered"] is None
    items = {i["key"]: i for i in p["items"]}
    assert list(items) == ["code", "checks", "verdict", "counts", "compile_output", "failing_test"]
    assert [k for k, i in items.items() if not i["required"]] == ["compile_output", "failing_test"]
    assert items["verdict"]["text"] == "Judge verdict: FAILED"
    assert items["counts"]["derived"] and "hidden inputs are secret" in items["counts"]["text"]
    assert SECRET not in items["code"]["text"]
    assert p["about"][0].startswith("Explains your submission of ") and p["about"][0].endswith(
        "(failed tests)."
    )
    assert (
        p["about"][1]
        == "One explanation is kept for each submission: asking again shows it and sends nothing."
    )

    r = explain(client, h, sid, p["context_fingerprint"])
    assert r.status_code == 200 and not r.json()["cached"], r.text
    [ctx] = rec.explanations
    c = ctx.failing_case
    assert ctx.code == items["code"]["text"] and analysis_text(ctx.analysis) == items["checks"]["text"]
    assert ctx.compile_output == items["compile_output"]["text"]
    assert (
        failing_test_text(c.index, c.input, c.expected, c.actual, c.exception, c.message, c.line, c.missing)
        == items["failing_test"]["text"]
    )
    [prompt] = rec.prompts
    for key in ("verdict", "counts"):
        assert items[key]["text"] in prompt
    assert f"<compiler_output>\n{items['compile_output']['text']}\n</compiler_output>" in prompt
    assert f"<failing_public_test>\n{items['failing_test']['text']}\n</failing_public_test>" in prompt
    assert f"<learner_code>\n{_numbered(items['code']['text'])}\n</learner_code>" in prompt
    # Asked again: the kept explanation, said in the preview; nothing sent.
    again = explain_preview(client, h, sid).json()
    assert again["already_answered"].startswith("This submission was explained before")
    assert explain(client, h, sid, again["context_fingerprint"]).json()["cached"] is True
    assert len(rec.prompts) == 1


def test_a_left_out_failing_test_never_reaches_the_coach_also_on_a_retry(client):
    h, rec = setup(client)
    sid = failed_submission(client)
    p = explain_preview(client, h, sid, compile_output=False, failing_test=False).json()
    assert [i["key"] for i in p["items"]] == ["code", "checks", "verdict", "counts"]
    assert [x["key"] for x in p["left_out"]] == ["compile_output", "failing_test"]
    assert OUTPUT_CANARY not in str(p) and COMPILE_CANARY not in str(p)
    r = explain(client, h, sid, p["context_fingerprint"], compile_output=False, failing_test=False)
    assert r.status_code == 200
    # A retry (the reply was lost) asking for more gets the kept explanation; nothing more is sent.
    wider = explain(client, h, sid, p["context_fingerprint"], compile_output=True, failing_test=True)
    assert wider.status_code == 200 and wider.json()["cached"] is True
    assert len(rec.prompts) == 1
    assert all(OUTPUT_CANARY not in x and COMPILE_CANARY not in x for x in rec.prompts)
    assert rec.explanations[0].failing_case is None and rec.explanations[0].compile_output is None


def test_a_wider_choice_than_approved_is_refused_before_anything_is_sent(client):
    h, rec = setup(client)
    sid = failed_submission(client)
    p = explain_preview(client, h, sid, failing_test=False).json()
    r = explain(client, h, sid, p["context_fingerprint"], failing_test=True)
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    assert rec.prompts == [] and interactions(client) == 0


def test_a_new_submission_is_explained_only_after_its_own_preview(client):
    h, rec = setup(client)
    first = failed_submission(client)
    p = explain_preview(client, h, first).json()
    second = failed_submission(client)  # submitted again before sending
    r = explain(client, h, second, p["context_fingerprint"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "context_changed"
    assert rec.prompts == []
    fresh = r.json()["error"]["details"]["preview"]
    ok = explain(client, h, second, fresh["context_fingerprint"])
    assert ok.status_code == 200 and ok.json()["submission_id"] == second
    assert len(rec.prompts) == 1


def test_hidden_tests_stay_hidden_counts_only(client):
    h, rec = setup(client)
    sid = failed_submission(client, leak_hidden=True)
    p = explain_preview(client, h, sid).json()
    assert HIDDEN_CANARY not in str(p)
    failing = next(i for i in p["items"] if i["key"] == "failing_test")
    assert '"test": 2' in failing["text"] and OUTPUT_CANARY in failing["text"]  # the public one
    explain(client, h, sid, p["context_fingerprint"])
    assert all(HIDDEN_CANARY not in x for x in rec.prompts)


def test_another_accounts_submission_reads_the_same_as_a_missing_one(client):
    setup(client, email="owner@example.com")
    theirs = failed_submission(client, email="owner@example.com")
    h, rec = setup(client, email="other@example.com")
    for sid in (theirs, "00000000-0000-0000-0000-000000000000"):
        a = explain_preview(client, h, sid)
        b = explain(client, h, sid, "x" * 20)
        assert a.status_code == b.status_code == 404
        assert a.json()["error"]["message"] == b.json()["error"]["message"] == "Submission not found"
    assert rec.prompts == []


def test_an_explanation_without_a_preview_sends_everything_as_before(client):
    h, rec = setup(client)
    sid = failed_submission(client)
    r = client.post(EXPLAIN, headers=h, json={"submission_id": sid})
    assert r.status_code == 200
    [ctx] = rec.explanations
    assert ctx.compile_output and ctx.failing_case is not None and ctx.failing_case.actual == OUTPUT_CANARY
