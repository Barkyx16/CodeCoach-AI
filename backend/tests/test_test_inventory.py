"""scripts/test_inventory.py (Volume 9, prompt 10): the runners' own collection, compared between a
baseline and a candidate. A replaced test or a file no runner collects fails; a rename is shown for
review; a deliberate removal can be accepted; there's no count gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("test_inventory", ROOT / "scripts" / "test_inventory.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["test_inventory"] = module
    spec.loader.exec_module(module)
    return module


inv = _load()

NAV = "vitest\tsrc/test/integration/returnPaths.test.tsx\t"
BASE = [
    NAV + "results keep Back to History after an item is chosen",
    NAV + "a career link opens that career's library when signed in",
    NAV + "an unsent scenario response asks before leaving",
    NAV + "goals return to the plan",
    "pytest\tbackend/tests/test_notes.py\ttest_create_note",
]


def test_a_file_overwritten_with_other_tests_is_caught_even_though_the_count_went_up():
    # The recovered mistake: four navigation tests replaced by new ones in the same file.
    cand = [BASE[-1]] + [NAV + f"focus returns to item {i}" for i in range(6)]
    report, failed = inv.compare(BASE, cand)
    assert failed
    assert len(report["removed_unaccepted"]) == 4
    assert report["renamed"] == []
    assert len(cand) > len(BASE)  # more tests, still a failure


def test_a_rename_is_shown_for_review_and_does_not_fail():
    cand = [*BASE[1:], NAV + "results keep 'Back to History' after an item is chosen"]
    report, failed = inv.compare(BASE, cand)
    assert not failed
    assert report["renamed"] == [(BASE[0], NAV + "results keep 'Back to History' after an item is chosen")]
    assert report["removed"] == []


def test_a_deliberate_removal_can_be_accepted_by_identity_or_whole_file():
    cand = BASE[1:4]
    report, failed = inv.compare(BASE, cand)
    assert failed and len(report["removed_unaccepted"]) == 2
    report, failed = inv.compare(
        BASE, cand, [BASE[0], "# merged into the History test", "file\tbackend/tests/test_notes.py"]
    )
    assert not failed and report["removed_unaccepted"] == [] and len(report["removed"]) == 2


def test_a_test_file_no_runner_collects_fails():
    collected = {NAV + "goals return to the plan"}
    on_disk = {
        "vitest": {"src/test/integration/returnPaths.test.tsx", "src/test/integration/forgotten.test.tsx"},
        "playwright": set(),
        "pytest": set(),
    }
    lost = inv.uncollected(collected, on_disk)
    assert lost == {"uncollected\tvitest\tsrc/test/integration/forgotten.test.tsx"}
    report, failed = inv.compare(BASE, [*BASE, *lost])
    assert failed and report["uncollected"] == sorted(lost)


def test_added_tests_alone_pass():
    report, failed = inv.compare(BASE, [*BASE, NAV + "a new check"])
    assert not failed and report["added"] == [NAV + "a new check"]


def test_parses_each_runners_own_collection_output(tmp_path):
    vitest = json.dumps(
        [
            {
                "name": "apiRequest > drops empty query params",
                "file": str(tmp_path / "frontend" / "src" / "api" / "client.test.ts"),
                "projectName": "app",
            }
        ]
    )
    assert inv.parse_vitest(vitest, tmp_path) == {
        "vitest\tsrc/api/client.test.ts\tapiRequest > drops empty query params"
    }
    # Two cases of one table that format to the same title are both counted.
    twins = json.dumps([{"name": "kinds > [ApiError: x] is invalid", "file": "src/lib/retry.test.ts"}] * 2)
    assert inv.parse_vitest(twins, tmp_path) == {
        "vitest\tsrc/lib/retry.test.ts\tkinds > [ApiError: x] is invalid",
        "vitest\tsrc/lib/retry.test.ts\tkinds > [ApiError: x] is invalid #2",
    }
    playwright = json.dumps(
        {
            "suites": [
                {
                    "title": "a11y.spec.ts",
                    "file": "a11y.spec.ts",
                    "specs": [
                        {
                            "title": "public pages",
                            "file": "a11y.spec.ts",
                            "tests": [{"projectName": "desktop"}, {"projectName": "mobile"}],
                        }
                    ],
                    "suites": [
                        {
                            "title": "signed in",
                            "file": "a11y.spec.ts",
                            "specs": [
                                {
                                    "title": "screens",
                                    "file": "a11y.spec.ts",
                                    "tests": [{"projectName": "desktop"}],
                                }
                            ],
                            "suites": [],
                        }
                    ],
                }
            ]
        }
    )
    assert inv.parse_playwright(playwright) == {
        "playwright\te2e/a11y.spec.ts\t[desktop] public pages",
        "playwright\te2e/a11y.spec.ts\t[mobile] public pages",
        "playwright\te2e/a11y.spec.ts\t[desktop] signed in > screens",
    }
    pytest_out = "tests/test_notes.py::test_create_note\ntests/test_x.py::test_y[case-1]\n\n2 tests collected in 0.1s\n"
    assert inv.parse_pytest(pytest_out) == {
        "pytest\tbackend/tests/test_notes.py\ttest_create_note",
        "pytest\tbackend/tests/test_x.py\ttest_y[case-1]",
    }


def test_compare_command_exit_status(tmp_path):
    base, cand, accept = tmp_path / "base.txt", tmp_path / "cand.txt", tmp_path / "accept.txt"
    base.write_text("\n".join(BASE) + "\n")
    cand.write_text("\n".join(BASE[1:]) + "\n")
    assert inv.main(["compare", str(base), str(cand)]) == 1
    accept.write_text(BASE[0] + "\n")
    assert inv.main(["compare", str(base), str(cand), "--accept", str(accept)]) == 0


def test_files_on_disk_include_names_a_runner_might_miss(tmp_path):
    for f in [
        "frontend/src/a.test.tsx",
        "frontend/src/sub/b.spec.tsx",  # vitest here only includes *.test.*: shows as uncollected
        "frontend/src/c.ts",
        "frontend/node_modules/x/d.test.ts",
        "frontend/e2e/e.spec.ts",
        "backend/tests/test_f.py",
        "backend/tests/g_test.py",
        "backend/tests/helpers.py",
    ]:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("")
    assert inv.files_on_disk(tmp_path) == {
        "vitest": {"src/a.test.tsx", "src/sub/b.spec.tsx"},
        "playwright": {"e2e/e.spec.ts"},
        "pytest": {"backend/tests/test_f.py", "backend/tests/g_test.py"},
    }
