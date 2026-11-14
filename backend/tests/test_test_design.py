"""Test design against authored faulty versions (Volume 10, prompt 4; docs/TEST_DESIGN.md).

Cases are checked before anything runs; they run in one sandbox job against the reference and every
faulty version; what each case tells apart is read off the real outputs (a local JDK stands in for
the sandbox here, the real gVisor judge is in test_judge_sandbox.py); a wrong expected output counts
against nothing; without a judge nothing is run or guessed; runs keep their version and owner.
Synthetic content and accounts only."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.content import validate
from app.models import TestDesignRun as RunRow
from app.services import test_design_judge
from app.services.judge.harness import build_driver, parse_driver_output
from app.services.judge.runner_client import RunnerUnavailable
from app.testdesign import BY_SLUG, SEED_DIR, variant_key
from app.worker import JudgeWorker

from .conftest import auth_headers, register
from .judge_fakes import TOKEN, FakeRunner, lines
from .local_java import LocalJavaRunner, jdk_available

BACKEND = Path(__file__).resolve().parents[1]
java = pytest.mark.skipif(not jdk_available(), reason="needs a local JDK (CI installs one)")
MINE = "/api/v1/me/test-design"
COUNT = "tests-count-in-range"
# Ordinary cases: values well inside or outside the range, the last value outside, lo <= hi.
NORMAL = [
    ({"nums": [1, 5, 9], "lo": 2, "hi": 8}, 1),
    ({"nums": [3, 40], "lo": 0, "hi": 10}, 1),
    ({"nums": [10, 20, 30], "lo": 15, "hi": 25}, 1),
    ({"nums": [-3, 0, 3], "lo": -10, "hi": -1}, 1),
    ({"nums": [7], "lo": 0, "hi": 5}, 0),
]


def case(inp: dict, expected, label: str | None = None) -> dict:
    return {"input": inp, "expected": expected, "label": label}


def client_with(make_client, runner, **settings):
    c = make_client(execution_enabled=True, runner_token=TOKEN, **settings)
    c.app.state.execution_health.probe = lambda: True
    worker = JudgeWorker(c.app.state.session_factory, runner, c.app.state.settings)
    return c, worker, auth_headers(register(c))


def run_cases(c, worker, h, cases, slug=COUNT, key=None):
    body = {"cases": cases, **({"client_request_id": key} if key else {})}
    made = c.post(f"{MINE}/{slug}/runs", json=body, headers=h)
    assert made.status_code in (200, 202), made.text
    while worker.process_one():
        pass
    return c.get(f"{MINE}/runs/{made.json()['id']}", headers=h).json()


def test_the_exercise_shows_the_specification_but_not_the_faulty_versions(client):
    listed = client.get("/api/v1/test-design").json()
    assert [e["slug"] for e in listed] == list(BY_SLUG)
    body = client.get(f"/api/v1/test-design/{COUNT}").json()
    ex = BY_SLUG[COUNT]
    assert body["variant_count"] == 4 and body["params"][0] == {"name": "nums", "type": "int[]"}
    assert body["limits"] == {"max_cases": 12, "max_length": 20, "min_value": -1000, "max_value": 1000}
    assert body["execution_enabled"] is False
    text = json.dumps(body) + json.dumps(listed)
    for v in ex.variants:
        assert v.id not in text and v.title not in text and v.defect not in text and v.gap not in text
    assert "v < hi" not in text and "class Solution" not in text  # no code at all
    shown = client.get(f"/api/v1/test-design/{COUNT}/variants").json()  # the deliberate reveal
    assert [(v["key"], v["title"]) for v in shown] == [
        (variant_key(k), v.title) for k, v in enumerate(ex.variants)
    ]
    assert "id" not in shown[0]
    assert client.get("/api/v1/test-design/no-such").status_code == 404


def test_malformed_or_oversized_cases_are_refused_with_plain_messages(client):
    h = auth_headers(register(client))
    url = f"{MINE}/{COUNT}/runs"
    bad = [
        case({"nums": "1,2", "lo": 0, "hi": 3}, 1),
        case({"nums": list(range(21)), "lo": 0, "hi": 3}, 1),
        case({"nums": [5000], "lo": 0, "hi": 3}, 1),
        case({"nums": [1], "hi": 3}, 1),
        case({"nums": [1], "lo": 0, "hi": 3, "extra": 1}, 1),
        case({"nums": [1], "lo": 0, "hi": 3}, "one"),
        case({"nums": [1], "lo": 0.5, "hi": 3}, 1),
    ]
    r = client.post(url, json={"cases": bad}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_cases"
    details = r.json()["error"]["details"]["cases"]
    assert details["1"] == ["nums: a list of whole numbers, like 3, -1, 7."]
    assert details["2"] == ["nums: at most 20 values (this has 21)."]
    assert details["3"] == ["nums: each value between -1000 and 1000."]
    assert details["4"] == ["lo: give a value."]
    assert details["5"] == ["Unknown parameter: extra."]
    assert details["6"] == ["Expected output: a whole number."]
    assert details["7"] == ["lo: a whole number."]
    many = client.post(
        url, json={"cases": [case({"nums": [i], "lo": 0, "hi": 3}, 1) for i in range(13)]}, headers=h
    )
    assert many.status_code == 422 and "At most 12 cases" in many.json()["error"]["message"]
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(RunRow)) == 0  # nothing saved


def test_without_a_judge_cases_are_saved_but_not_run(client):
    h = auth_headers(register(client))
    r = client.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h)
    assert r.status_code == 202
    run = r.json()
    assert run["status"] == "not_run" and run["report"] is None
    assert "weren't run" in run["status_detail"] and "nothing was guessed" in run["status_detail"]
    assert run["cases"][0]["input"] == NORMAL[0][0] and run["exercise_version"] == 1


def test_a_judge_that_is_down_refuses_and_saves_nothing(make_client):
    c, _, h = client_with(make_client, FakeRunner(lambda f, n: ("ok", "", {})))
    c.app.state.execution_health.probe = lambda: False
    r = c.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "judge_unavailable"
    with c.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(RunRow)) == 0


@java
def test_one_boundary_case_tells_apart_what_many_ordinary_cases_dont(make_client):
    c, worker, h = client_with(make_client, LocalJavaRunner())
    ordinary = run_cases(c, worker, h, [case(i, e, "equivalence") for i, e in NORMAL])
    rep = ordinary["report"]
    assert ordinary["status"] == "done" and (rep["caught"], rep["total"]) == (0, 4)
    assert all(row["status"] == "counted" and row["distinguishes"] == [] for row in rep["cases"])
    assert "added nothing new" in " ".join(rep["summary"])
    assert "only the 4 faulty versions written for this exercise" in rep["summary"][1]
    assert rep["gap"]["variant"] == "A" and "equals one of the bounds" in rep["gap"]["hint"]
    assert all(v["title"] is None for v in rep["variants"])  # nothing caught, nothing named

    boundary = run_cases(c, worker, h, [case({"nums": [3, 7], "lo": 1, "hi": 7}, 2, "boundary")])
    rep = boundary["report"]
    assert rep["caught"] == 2 and rep["cases"][0]["distinguishes"] == ["A", "C"]
    assert rep["variants"][0]["title"] == "Leaves out values equal to hi"
    assert rep["variants"][1]["title"] is None  # not caught: still hidden
    assert ordinary["id"] != boundary["id"]  # a distinct attempt; the earlier one is unchanged
    assert c.get(f"{MINE}/runs/{ordinary['id']}", headers=h).json()["report"]["caught"] == 0


@java
def test_the_report_matches_each_implementation_run_on_its_own(make_client):
    """The one-job run puts every implementation in one file; running each alone must agree."""
    c, worker, h = client_with(make_client, LocalJavaRunner())
    cases = [case(i, e) for i, e in NORMAL[:2]] + [
        case({"nums": [2, 5], "lo": 2, "hi": 9}, 2),
        case({"nums": [4], "lo": 6, "hi": 2}, 0),
        case({"nums": [0, 4], "lo": 3, "hi": 5}, 1),
    ]
    rep = run_cases(c, worker, h, cases)["report"]
    ex = BY_SLUG[COUNT]
    alone = LocalJavaRunner()
    outputs = []
    for _, code in ex.implementations():
        raw = alone.run(
            {"Solution.java": code, "Main.java": build_driver(ex.signature, [x["input"] for x in cases])},
            "n0nce",
            5,
        )
        got = parse_driver_output(raw.stdout, "n0nce")
        outputs.append([got[i].get("output") for i in range(len(cases))])
    for i, row in enumerate(rep["cases"]):
        expected = [variant_key(k) for k in range(len(ex.variants)) if outputs[k + 1][i] != outputs[0][i]]
        assert row["distinguishes"] == expected, i
        assert row["reference_output"] == str(outputs[0][i])
    assert rep["caught"] == 3  # no case has a value equal to hi, so version A stays hidden
    assert rep["variants"][0]["caught_by"] == [] and rep["gap"]["variant"] == "A"


@java
def test_a_wrong_expected_output_counts_against_nothing_and_a_correct_version_is_never_called_faulty(
    make_client, monkeypatch
):
    ex = BY_SLUG[COUNT]
    correct = dataclasses.replace(
        ex.variants[0],
        id="correct-rewrite",
        title="A correct rewrite",
        code=ex.reference.replace("if (v >= lo && v <= hi)", "if (!(v < lo) && !(v > hi))"),
    )
    monkeypatch.setitem(BY_SLUG, COUNT, dataclasses.replace(ex, variants=(*ex.variants, correct)))
    c, worker, h = client_with(make_client, LocalJavaRunner())
    run = run_cases(
        c,
        worker,
        h,
        [
            case({"nums": [3, 7], "lo": 1, "hi": 7}, 1),  # the reference returns 2
            case({"nums": [4], "lo": 6, "hi": 2}, 0),
            case({"nums": [2, 5], "lo": 2, "hi": 9}, 2),
            case({"nums": [0, 4], "lo": 3, "hi": 5}, 1),
            case({"nums": [3, 7], "lo": 0, "hi": 9}, 2),
        ],
    )
    rep = run["report"]
    wrong = rep["cases"][0]
    assert wrong["status"] == "disagrees" and wrong["distinguishes"] == []
    assert "reference returns 2 here, not 1" in wrong["notes"][0]
    assert rep["variants"][4] == {"key": "E", "caught_by": [], "title": None}  # the correct rewrite
    assert all("E" not in row["distinguishes"] for row in rep["cases"])
    assert "1 case had an expected output that disagrees" in " ".join(rep["summary"])


@java
def test_duplicates_are_named_and_run_once(make_client):
    runner = LocalJavaRunner()
    c, worker, h = client_with(make_client, runner)
    same = {"nums": [3, 7], "lo": 1, "hi": 7}
    rep = run_cases(c, worker, h, [case(same, 2), case(NORMAL[0][0], 1), case(same, 2)])["report"]
    assert rep["cases"][2]["status"] == "duplicate" and "Same input as case 1" in rep["cases"][2]["notes"][0]
    main = runner.calls[-1]["files"]["Main.java"]
    assert main.count("run(out, prefix,") == 2 * 5  # two distinct inputs x (reference + 4 versions)


def test_results_that_never_arrived_are_not_guessed(make_client):
    # The sandbox stops at the time limit after the reference's two results and one version's.
    def script(files, nonce):
        return "timeout", lines(nonce, [2, 1, 1]), {"exit_code": None}

    c, worker, h = client_with(make_client, FakeRunner(script))
    run = run_cases(c, worker, h, [case({"nums": [3, 7], "lo": 1, "hi": 7}, 2), case(*NORMAL[0])])
    rep = run["report"]
    assert run["status"] == "done"
    assert rep["summary"][1] == "The run hit the time limit before every result arrived."
    assert rep["caught"] == 1 and rep["cases"][0]["distinguishes"] == ["A"]
    assert "3 versions didn't finish on this input" in " ".join(rep["cases"][0]["notes"])
    assert rep["gap"] is None


def test_runner_failures_are_retried_then_reported_without_a_result(make_client):
    c, worker, h = client_with(make_client, FakeRunner(lambda f, n: RunnerUnavailable("down")))
    run = run_cases(c, worker, h, [case(*NORMAL[0])])
    assert run["status"] == "failed" and run["report"] is None
    assert "Nothing was guessed" in run["status_detail"]
    with c.app.state.session_factory() as db:
        assert db.scalar(select(RunRow.attempts)) == c.app.state.settings.judge_max_attempts


def test_a_resend_returns_the_same_run_and_a_reused_key_is_refused(make_client):
    c, _, h = client_with(make_client, FakeRunner(lambda f, n: ("ok", "", {})))
    body = {"cases": [case(*NORMAL[0])], "client_request_id": "td-key-000001"}
    first = c.post(f"{MINE}/{COUNT}/runs", json=body, headers=h)
    again = c.post(f"{MINE}/{COUNT}/runs", json=body, headers=h)
    assert (first.status_code, again.status_code) == (202, 200) and first.json()["id"] == again.json()["id"]
    other = c.post(f"{MINE}/{COUNT}/runs", json={**body, "cases": [case(*NORMAL[1])]}, headers=h)
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_key_reused"
    pending = c.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[1])]}, headers=h)
    assert pending.status_code == 429 and pending.json()["error"]["code"] == "test_run_pending"
    assert pending.json()["error"]["details"]["pending_run_id"] == first.json()["id"]


def test_a_run_keeps_its_version_and_isnt_run_against_a_changed_exercise(make_client, monkeypatch):
    c, worker, h = client_with(make_client, FakeRunner(lambda f, n: ("ok", lines(n, [1] * 5), {})))
    done = run_cases(c, worker, h, [case(*NORMAL[0])])
    assert done["status"] == "done" and done["exercise_version"] == 1
    queued = c.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[1])]}, headers=h).json()
    monkeypatch.setitem(BY_SLUG, COUNT, dataclasses.replace(BY_SLUG[COUNT], version=2))
    while worker.process_one():
        pass
    changed = c.get(f"{MINE}/runs/{queued['id']}", headers=h).json()
    assert changed["status"] == "failed" and changed["status_detail"] == test_design_judge.CHANGED_DETAIL
    kept = c.get(f"{MINE}/runs/{done['id']}", headers=h).json()
    assert (kept["exercise_version"], kept["current_version"]) == (1, 2) and kept["report"] == done["report"]


def test_runs_are_yours_exported_and_deleted_with_the_account(client):
    data = register(client)
    h = auth_headers(data)
    made = client.post(
        f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0], "boundary")]}, headers=h
    ).json()
    other = auth_headers(register(client, email="bea@example.com"))
    assert client.get(f"{MINE}/runs/{made['id']}", headers=other).status_code == 404
    assert client.get(f"{MINE}/{COUNT}/runs", headers=other).json() == []
    exported = client.get("/api/v1/me/export", headers=h).json()["test_design_runs"]
    assert exported[0]["cases"][0]["label"] == "boundary" and exported[0]["status"] == "not_run"
    gone = client.request(
        "DELETE", "/api/v1/auth/me", headers=h, json={"password": "CorrectHorse42", "confirm": "DELETE"}
    )
    assert gone.status_code == 204
    with client.app.state.session_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(RunRow).where(RunRow.user_id == data["user"]["id"]))
            == 0
        )


def test_the_validator_rejects_a_broken_fixture(tmp_path, monkeypatch):
    good = json.loads((SEED_DIR / "001-tests-count-in-range.json").read_text())
    bad = json.loads(json.dumps(good))
    bad["slug"] = "tests-broken"
    bad["examples"][0]["input"]["nums"] = [5000]
    bad["variants"][0]["gap"] = ""
    bad["variants"][1]["code"] = "import java.util.*;\n" + bad["variants"][1]["code"]
    bad["variants"][2]["witness"] = {"nums": [1]}
    (tmp_path / "001-tests-broken.json").write_text(json.dumps(bad))
    shape = {
        **good,
        "slug": "tests-shape",
        "signature": {"method": "f", "params": [{"name": "s", "type": "String"}], "returns": "int"},
    }
    (tmp_path / "002-tests-shape.json").write_text(json.dumps(shape))
    (tmp_path / "003-x.json").write_text(json.dumps({**good, "slug": "count-in-range"}))
    monkeypatch.setattr(validate, "TEST_DESIGN_DIR", tmp_path)
    errors = "\n".join(validate.run(None).errors)
    assert "test design tests-broken: example 1: nums: each value between -1000 and 1000." in errors
    assert "faulty version exclusive-upper: missing ['gap']" in errors
    assert "faulty version exclusive-lower: can't use import, package or a public class" in errors
    assert "faulty version skips-last: witness: lo: give a value." in errors
    assert "test design tests-shape: the one supported shape is int[] then up to two int" in errors
    assert "a test design exercise's slug starts with 'tests-'" in errors
    monkeypatch.setattr(validate, "TEST_DESIGN_DIR", SEED_DIR)
    assert not [e for e in validate.run(None).errors if "test design" in e]


def _verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_ref", BACKEND / "scripts" / "verify_reference_solutions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@java
def test_every_exercise_passes_the_jdk_check():
    verify = _verifier()
    for path in sorted(SEED_DIR.glob("*.json")):
        assert verify.check_test_design_exercise(path) == [], path.name


@java
def test_the_jdk_check_refuses_an_inconsistent_fixture(tmp_path):
    verify = _verifier()
    good = json.loads((SEED_DIR / "001-tests-count-in-range.json").read_text())

    def check(data: dict, timeout_s: float = 60.0) -> str:
        path = tmp_path / "x.json"
        path.write_text(json.dumps(data))
        return "\n".join(verify.check_test_design_exercise(path, timeout_s))

    wrong_example = json.loads(json.dumps(good))
    wrong_example["examples"][0]["expected"] = 2  # a made-up expected output
    assert "example 1 expects 2, but the reference returns 1" in check(wrong_example)
    same = json.loads(json.dumps(good))
    same["variants"][3]["code"] = good["reference"]  # a "faulty" version that isn't
    assert "faulty version swaps-reversed-range gives the reference's answer on its own witness" in check(
        same
    )
    crashy = json.loads(json.dumps(good))
    crashy["reference"] = good["reference"].replace("if (lo > hi) {", "if (nums[0] > hi && lo > hi) {")
    assert "the reference throws ArrayIndexOutOfBoundsException" in check(crashy)
    hang = json.loads(json.dumps(good))
    hang["variants"][0]["code"] = good["variants"][0]["code"].replace(
        "int count = 0;", "int count = 0;\n        while (nums.length == 0) { }"
    )
    assert "didn't finish within 5 s" in check(hang, timeout_s=5)
    easy = json.loads(json.dumps(good))
    easy["examples"].append({"input": {"nums": [3, 7], "lo": 1, "hi": 7}, "expected": 2})
    easy["examples"].append({"input": {"nums": [2, 5], "lo": 2, "hi": 9}, "expected": 2})
    easy["examples"].append({"input": {"nums": [4], "lo": 6, "hi": 2}, "expected": 0})
    assert "the examples already tell every faulty version apart" in check(easy)


def test_a_stale_running_run_is_put_back_or_failed(make_client):
    c, worker, h = client_with(make_client, FakeRunner(lambda f, n: ("ok", "", {})))
    made = c.post(f"{MINE}/{COUNT}/runs", json={"cases": [case(*NORMAL[0])]}, headers=h).json()
    with c.app.state.session_factory() as db:
        run = test_design_judge.claim(db)
        assert run is not None and run.id == made["id"]
        run.judge_started_at = run.judge_started_at.replace(year=2000)
        db.commit()
    with c.app.state.session_factory() as db:
        assert test_design_judge.recover_stale(db, c.app.state.settings) == 1
    assert c.get(f"{MINE}/runs/{made['id']}", headers=h).json()["status"] == "queued"
