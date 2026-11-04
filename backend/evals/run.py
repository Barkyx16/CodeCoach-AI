"""AI coach evaluation suite: measure before claiming accuracy (docs/AI_EVALUATION.md).

    python -m evals.run                                  # offline, deterministic, free (what CI runs)
    python -m evals.run --split dev                      # development sets only
    python -m evals.run --gate results/offline.json      # check a report against the release gates
    python -m evals.run --compare BASELINE.json CANDIDATE.json
    python -m evals.run --check-report results/offline.json   # does it belong to this commit and data?
    # Claude: deliberate, budgeted and labelled as an external run; never in CI
    AI_PROVIDER=anthropic ANTHROPIC_API_KEY=… python -m evals.run --provider anthropic \\
        --allow-paid-calls --max-calls 200 [--price-input-per-mtok X --price-output-per-mtok Y --price-source URL]

What it measures
----------------
Code review (evals/review_set.json for tuning; holdout_set.json and medium_set.json held out):
issue precision/recall/F1 per category, false alarms on clean code, Big-O accuracy, schema
validity. Hints, for every problem: level-1 spoilers, level-2 relevance, code in levels 1-2.
Career answers (evals/career_dev.json, career_holdout.json): the written-answer coach against
labelled answers, per case and check (evals/career.py). Requests to Claude, without calling it
(evals/contracts.py). Provider failures and the offline fallback (evals/faults.py).

Every report records the commit, datasets and their hashes, rubric and prompt versions, provider,
model, configuration and times (evals/meta.py), and says whether the run was complete. Results
go to evals/results/<label>.json and .md with the same run id. The numbers describe these
labelled sets only; they are not general accuracy claims.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.db.seed import load_seed_files  # noqa: E402
from app.schemas.ai import CodeReview, HintContent  # noqa: E402
from app.services.ai.base import (  # noqa: E402
    CoachProvider,
    HintContext,
    ProblemContext,
    ProviderError,
    ProviderResult,
    ReviewContext,
)
from app.services.ai.interviewer_offline import normalize_big_o  # noqa: E402
from app.services.ai.offline import OfflineCoach  # noqa: E402
from app.services.ai.service import build_provider, sanitize_code  # noqa: E402
from app.services.ai.static_analysis import analyze  # noqa: E402
from evals import career, meta  # noqa: E402
from evals.gates import compare, evaluate_gates  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CATEGORIES = ["correctness", "edge-case", "complexity", "readability", "style"]
_CODE_LIKE = re.compile(r"(;\s*$|;\s*\n|\{\s*\n|\breturn\s+\w+\s*;|\bpublic\s+\w+)", re.M)
SECTIONS = ("coding", "career", "contracts", "faults")


def problem_contexts() -> dict[str, ProblemContext]:
    out = {}
    for p in load_seed_files():
        out[p["slug"]] = ProblemContext(
            slug=p["slug"],
            title=p["title"],
            statement=p["statement"],
            constraints=p["constraints"],
            signature=p["signature"],
            starter_code=p["starter_code"],
            expected_time=p["expected_complexity"].get("time"),
            expected_space=p["expected_complexity"].get("space"),
            curated_hints=p["hints"],
        )
    return out


# --- usage and budget -------------------------------------------------------------------------


class BudgetExhausted(Exception):
    pass


class Metered:
    """Wraps a provider to count calls, tokens, latency and failures, and to stop at a budget."""

    def __init__(self, inner: CoachProvider, max_calls: int | None = None) -> None:
        self.inner, self.max_calls = inner, max_calls
        self.name, self.model = inner.name, inner.model
        self.calls = self.failures = self.input_tokens = self.output_tokens = 0
        self.latencies: list[float] = []

    def _call(self, fn: Callable[[], ProviderResult]) -> ProviderResult:
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise BudgetExhausted(f"stopped at the budget of {self.max_calls} calls")
        self.calls += 1
        start = time.perf_counter()
        try:
            result = fn()
        except ProviderError:
            self.failures += 1
            raise
        finally:
            self.latencies.append((time.perf_counter() - start) * 1000)
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        return result

    def hint(self, ctx: HintContext) -> ProviderResult[HintContent]:
        return self._call(lambda: self.inner.hint(ctx))

    def review(self, ctx: ReviewContext) -> ProviderResult[CodeReview]:
        return self._call(lambda: self.inner.review(ctx))

    def usage(self, prices: dict | None) -> dict:
        lat = sorted(self.latencies)
        cost = None
        if prices:
            cost = round(
                self.input_tokens / 1e6 * prices["input_per_mtok"]
                + self.output_tokens / 1e6 * prices["output_per_mtok"],
                4,
            )
        return {
            "calls": self.calls,
            "failures": self.failures,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms_p50": round(statistics.median(lat), 2) if lat else None,
            "latency_ms_max": round(lat[-1], 2) if lat else None,
            "cost_usd": cost,
            "cost_basis": prices
            or "no prices given; cost is not estimated (pass --price-input-per-mtok/--price-output-per-mtok from your actual pricing)",
        }


# --- code review and hints --------------------------------------------------------------------


@dataclass
class ReviewScores:
    tp: Counter = field(default_factory=Counter)
    fp: Counter = field(default_factory=Counter)
    fn: Counter = field(default_factory=Counter)
    clean_samples: int = 0
    clean_false_alarms: int = 0
    complexity_hits: int = 0
    schema_valid: int = 0
    provider_errors: int = 0
    total: int = 0
    misses: list[dict] = field(default_factory=list)


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": _r(p), "recall": _r(r), "f1": _r(f), "tp": tp, "fp": fp, "fn": fn}


def _r(x: float | None) -> float | None:
    return round(x, 3) if x is not None else None


def evaluate_reviews(
    provider: CoachProvider, samples: list[dict], problems: dict[str, ProblemContext]
) -> dict:
    s = ReviewScores()
    for sample in samples:
        problem = problems[sample["problem"]]
        code = sanitize_code(sample["code"], 12_000)
        ctx = ReviewContext(
            problem=problem,
            code=code,
            judge_status=None,
            analysis=analyze(
                code,
                signature=problem.signature,
                starter_code=problem.starter_code,
                expected_time=problem.expected_time,
                constraints=problem.constraints,
            ),
        )
        s.total += 1
        try:
            result = provider.review(ctx)
            review = CodeReview.model_validate(result.content.model_dump())
            s.schema_valid += 1
        except ProviderError:
            s.provider_errors += 1  # counted against schema validity
            continue
        except Exception:  # noqa: BLE001 - counted as a schema failure
            continue
        predicted = {i.category for i in review.issues}
        expected = set(sample["categories"])
        for c in CATEGORIES:
            if c in predicted and c in expected:
                s.tp[c] += 1
            elif c in predicted:
                s.fp[c] += 1
            elif c in expected:
                s.fn[c] += 1
        if not expected:
            s.clean_samples += 1
            if any(i.severity in ("medium", "high") for i in review.issues):
                s.clean_false_alarms += 1
        if normalize_big_o(review.complexity.time.strip("O()")) == normalize_big_o(
            sample["time"].strip("O()")
        ):
            s.complexity_hits += 1
        if predicted != expected:
            s.misses.append(
                {
                    "id": sample["id"],
                    "expected": sorted(expected),
                    "predicted": sorted(predicted),
                    "time_expected": sample["time"],
                    "time_predicted": review.complexity.time,
                }
            )
    per_category = {c: _prf(s.tp[c], s.fp[c], s.fn[c]) for c in CATEGORIES}
    micro = _prf(sum(s.tp.values()), sum(s.fp.values()), sum(s.fn.values()))
    return {
        "samples": s.total,
        "schema_validity": _r(s.schema_valid / s.total) if s.total else None,
        "provider_errors": s.provider_errors,
        "issue_detection_micro": micro,
        "issue_detection_by_category": per_category,
        "clean_samples": s.clean_samples,
        "false_alarm_rate_on_clean_code": _r(s.clean_false_alarms / s.clean_samples)
        if s.clean_samples
        else None,
        "complexity_accuracy": _r(s.complexity_hits / s.total) if s.total else None,
        "disagreements": s.misses,
    }


def _mentions(text: str, term: str) -> bool:
    """Whole-word match, so the variable name "mid" doesn't match the word "middle"."""
    return re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text) is not None


def evaluate_hints(provider: CoachProvider, problems: dict[str, ProblemContext], terms: dict) -> dict:
    """Spoiler and relevance rates need hand-labeled terms, so they're measured on the labeled
    problems (hint_terms.json). The code-leak check needs no labels and runs on every problem."""
    spoilers, relevant, code_leaks, checked, labeled, errors = [], 0, [], 0, 0, 0
    for slug, problem in problems.items():
        t = terms.get(slug)
        labeled += t is not None
        starter = problem.starter_code
        for level in (1, 2):
            ctx = HintContext(problem=problem, code=starter, level=level, analysis=analyze(starter))
            try:
                hint: HintContent = provider.hint(ctx).content
            except ProviderError:
                errors += 1
                continue
            text = hint.hint.lower()
            checked += 1
            if t and level == 1 and any(_mentions(text, term) for term in t["level1_spoilers"]):
                spoilers.append(slug)
            if t and level == 2 and any(_mentions(text, term) for term in t["level2_concepts"]):
                relevant += 1
            if _CODE_LIKE.search(hint.hint):
                code_leaks.append(f"{slug}:L{level}")
    return {
        "problems": len(problems),
        "labeled_problems": labeled,
        "provider_errors": errors,
        "level1_spoiler_rate": _r(len(spoilers) / labeled) if labeled else None,
        "level1_spoilers": spoilers,
        "level2_relevance": _r(relevant / labeled) if labeled else None,
        "code_leak_rate_levels_1_2": _r(len(code_leaks) / checked) if checked else None,
        "code_leaks": code_leaks,
    }


# --- the run ----------------------------------------------------------------------------------


GRADER_PATH = "backend/app/careers/grading.py"


def load_grader(source: str) -> tuple[career.Grader, str, str]:
    """The grade() of another rubric: `git:<commit>` (that commit's app/careers/grading.py) or a file."""
    if source.startswith("git:"):
        rev = source.removeprefix("git:")
        text = subprocess.check_output(["git", "show", f"{rev}:{GRADER_PATH}"], cwd=EVAL_DIR, text=True)
        # The rubric's patterns live in questions.py, and graders read them from the question they
        # are given; rubric v5 also reads contradictions.py. An old grading.py with today's version
        # of either would not be the old rubric.
        modules = ["questions.py"] + (["contradictions.py"] if "contradictions" in text else [])
        for module in modules:
            same = (
                subprocess.run(
                    ["git", "diff", "--quiet", rev, "--", f":(top)backend/app/careers/{module}"], cwd=EVAL_DIR
                ).returncode
                == 0
            )
            if not same:
                raise SystemExit(
                    f"app/careers/{module} changed since {rev}, so its grading.py alone isn't that rubric. "
                    f"Run the harness of that commit instead: git worktree add /tmp/at-{rev} {rev}, then "
                    "python -m evals.run there with the same datasets, and --compare the two reports."
                )
        tmp = Path(tempfile.mkdtemp(prefix="career-grader-")) / "grading.py"
        tmp.write_text(text, encoding="utf-8")
        grader, version, _ = load_grader(str(tmp))
        return grader, version, f"git {rev}:{GRADER_PATH} (sha256 {meta.sha256_file(tmp)[:16]})"
    path = source
    spec = importlib.util.spec_from_file_location("career_grader_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while being defined
    spec.loader.exec_module(module)
    return (
        module.grade,
        str(getattr(module, "RUBRIC_VERSION", "unknown")),
        f"file {path} (sha256 {meta.sha256_file(Path(path))[:16]})",
    )


def data_checks() -> dict:
    """Dataset integrity, by id only (safe to run over sealed sets): every case file is valid
    under the protocol, and every cross-split near-duplicate has a recorded review."""
    from evals import overlap
    from evals.validate_cases import validate

    validation = {}
    for d in meta.manifest()["datasets"]:
        if d["domain"] == "career-answer" and d.get("protocol_version"):
            errors, _ = validate(career.load(d["file"]))
            validation[d["id"]] = errors
    pairs = overlap.flagged_pairs(overlap.all_items())
    return {
        "validation": validation,
        "flagged_pairs": len(pairs),
        "unreviewed_pairs": [f"{p['a']} ~ {p['b']} ({p['kind']})" for p in overlap.unreviewed(pairs)],
    }


def run(
    provider_name: str = "offline",
    *,
    split: str = "all",
    sections: tuple[str, ...] = SECTIONS,
    career_grader: tuple[career.Grader, str, str] | None = None,
    limit: int | None = None,
    max_calls: int | None = None,
    prices: dict | None = None,
    sealed: bool = False,
) -> dict:
    """Run the evaluation. `limit` keeps only the first N cases of each set: a partial run, and
    the report says so. `sealed` grades only the sealed sets (career section only): the final,
    once-only measurement of a frozen candidate (docs/EVAL_PROTOCOL.md)."""
    if sealed:
        sections, split = ("career",), "all"
    from app.careers import grading

    splits = {"dev"} if split == "dev" else {"holdout"} if split == "holdout" else {"dev", "holdout"}
    if provider_name == "offline":
        provider: CoachProvider = OfflineCoach()
    else:
        provider = build_provider(Settings())  # reads AI_PROVIDER / ANTHROPIC_API_KEY from the environment
        if provider.name != provider_name:
            raise SystemExit(f"Provider {provider_name!r} is not configured (got {provider.name!r}).")
    metered = Metered(provider, max_calls)
    grade, rubric_version, grader_desc = career_grader or (
        grading.grade,
        grading.RUBRIC_VERSION,
        f"app.careers.grading.grade (rubric {grading.RUBRIC_VERSION})",
    )
    config: dict[str, Any] = {"career_grader": grader_desc}
    if provider.name == "anthropic":
        config |= {
            "effort": getattr(provider, "effort", None),
            "sampling": "provider defaults (no temperature set)",
        }
        config |= {"max_calls": max_calls}
    else:
        config |= {"sampling": "none: the offline coach is deterministic"}
    report: dict = {
        "meta": meta.run_metadata(
            provider=provider.name,
            model=provider.model,
            config=config,
            sections=list(sections),
            selection={"split": split, "limit_per_set": limit},
        )
    }
    report["meta"]["rubric_version"] = rubric_version
    report["version_problems"] = meta.manifest_problems() + meta.prompt_version_problems()
    incomplete: list[str] = []
    if limit is not None:
        incomplete.append(f"only the first {limit} cases of each set were run")
    start = time.perf_counter()

    def take(items: list) -> list:
        return items[:limit] if limit is not None else items

    try:
        if "coding" in sections:
            problems = problem_contexts()
            if "dev" in splits:
                samples = json.loads((EVAL_DIR / "review_set.json").read_text())["samples"]
                # review_set.json was used while improving the offline rules: optimistic.
                report["review"] = evaluate_reviews(metered, take(samples), problems)
                terms = json.loads((EVAL_DIR / "hint_terms.json").read_text())
                hint_problems = dict(take(list(problems.items())))
                report["hints"] = evaluate_hints(metered, hint_problems, terms)
            if "holdout" in splits:
                for key, name in (
                    ("review_holdout", "holdout_set.json"),
                    ("review_medium", "medium_set.json"),
                ):
                    samples = json.loads((EVAL_DIR / name).read_text())["samples"]
                    report[key] = evaluate_reviews(metered, take(samples), problems)
        if "career" in sections:
            report["career"] = {}
            for d in meta.manifest()["datasets"]:
                # Sealed sets are graded only by a sealed run, and a sealed run grades nothing else.
                if (
                    d["domain"] != "career-answer"
                    or bool(d.get("sealed")) != sealed
                    or d["split"] not in splits
                ):
                    continue
                data = career.load(d["file"])
                data = {**data, "cases": take(data["cases"])}
                result = career.evaluate_set(data, grade)
                result["protocol_metrics"] = career.protocol_metrics(data, result)
                result["exposure"] = d.get("exposure")
                report["career"][data["id"]] = result
            if not sealed:
                report["regression"] = career.evaluate_regression(grade)
        if "contracts" in sections:
            from evals.contracts import run_contracts

            report["contracts"] = run_contracts()
        if "faults" in sections:
            from evals.faults import run_faults

            logging.getLogger("codecoach.ai.anthropic").setLevel(logging.ERROR)  # the faults are on purpose
            report["faults"] = run_faults()
    except BudgetExhausted as exc:
        incomplete.append(str(exc))
    report["kind"] = "sealed" if sealed else "development"
    if not sealed:
        report["data_checks"] = data_checks()
    for missing in set(SECTIONS) - set(sections) if not sealed else ():
        incomplete.append(f"section {missing!r} not run")
    if split != "all":
        incomplete.append(f"only the {split} split was run")
    report["usage"] = metered.usage(prices)
    report["duration_s"] = round(time.perf_counter() - start, 2)
    report["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    report["complete"] = not incomplete
    report["incomplete_reasons"] = incomplete
    report["gates"] = evaluate_gates(report)
    return report


# --- reports ----------------------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def to_markdown(r: dict) -> str:
    m = r["meta"]
    lines = [f"# Coach evaluation: `{m['provider']}` ({m['model']})", ""]
    if not r["complete"]:
        lines += [
            "> **PARTIAL RUN, not a benchmark result.** " + "; ".join(r["incomplete_reasons"]) + ".",
            "",
        ]
    lines += [
        f"Run `{m['run_id']}`, {m['started_at']} to {r['finished_at']} ({r['duration_s']} s), commit "
        f"`{(m['commit'] or 'unknown')[:12]}`{' with uncommitted changes' if m['uncommitted_changes'] else ''}. "
        f"Rubric {m['rubric_version']}, prompt {m['prompt_version']} (fingerprint `{m['prompt_fingerprint'][:12]}`). "
        f"{m['config']['sampling'].capitalize()}. These numbers describe these labelled sets only.",
        "",
        "| Dataset | Version | Split | sha256 |",
        "|---|---|---|---|",
        *(
            f"| {d['id']} | {d['version']} | {d['split']} | `{d['sha256_actual'][:12]}`{'' if d['matches_manifest'] else ' (differs from manifest)'} |"
            for d in m["datasets"]
        ),
        "",
        "## Release gates",
        "",
        "| Gate | Result | Why it exists |",
        "|---|---|---|",
    ]
    for g in r["gates"]:
        status = {"passed": "passed", "failed": f"**FAILED** ({len(g['failures'])})", "not run": "not run"}[
            g["status"]
        ]
        lines.append(f"| `{g['id']}` | {status} | {g['why']} |")
    failing = [g for g in r["gates"] if g["status"] == "failed"]
    if failing:
        lines += ["", "### What failed", ""]
        for g in failing:
            lines.append(f"- `{g['id']}`")
            lines += [f"  - {f}" for f in g["failures"][:12]]
            if len(g["failures"]) > 12:
                lines.append(f"  - … {len(g['failures']) - 12} more in the JSON report")
    lines.append("")
    lines += _career_markdown(r)
    lines += _regression_markdown(r)
    lines += _coding_markdown(r)
    if r.get("contracts"):
        c = r["contracts"]
        lines += [
            "## Requests to Claude (checked without calling it)",
            "",
            f"{c['requests_recorded']} requests built by the real prompt builders and service; hidden-test checks on "
            f"{c['problems_checked_for_hidden_data']} problems ({c['problems_without_distinctive_hidden_data']} have no hidden "
            "value distinct from their public data, so a leak there couldn't be detected).",
            "",
            "| Check | Result |",
            "|---|---|",
            *(
                f"| {k} | {'passed' if v['passed'] else f'FAILED ({len(v["failures"])})'} |"
                for k, v in c["checks"].items()
            ),
            "",
        ]
    if r.get("faults"):
        f = r["faults"]
        lim = f["client_limits"]
        lines += [
            "## Provider failures",
            "",
            f"{f['passed']} of {f['checks']} scenario × action checks fell back to the offline coach "
            f"({f['scenarios']} failure kinds × hint, review, explain-failure). Real client limits: "
            f"{lim['timeout_s']:.0f} s timeout, {lim['max_retries']} retries.",
            "",
        ]
        lines += [f"- {x['scenario']} during {x['action']}: {x['problem']}" for x in f["failed"]]
        lines.append("")
    u = r["usage"]
    lines += [
        "## Usage",
        "",
        f"{u['calls']} provider calls, {u['failures']} failed, {u['input_tokens']} input and {u['output_tokens']} output tokens, "
        f"latency p50 {u['latency_ms_p50']} ms, max {u['latency_ms_max']} ms. Cost: "
        + (f"${u['cost_usd']} ({u['cost_basis']})" if u["cost_usd"] is not None else str(u["cost_basis"]))
        + ".",
        "",
    ]
    return "\n".join(lines) + "\n"


def _career_markdown(r: dict) -> list[str]:
    sets = r.get("career") or {}
    if not sets:
        return []
    lines = ["## Career answers (written-answer coach)", ""]
    for set_id, s in sets.items():
        a = s["point_agreement"]
        lines += [
            f"### {set_id} ({s['split']}, {s['cases_scored']} of {s['cases_planned']} cases, track {s['track']})",
            "",
            f"Rubric points, grader vs labels: precision {_pct(a['precision'])}, recall {_pct(a['recall'])}, "
            f"accuracy {_pct(a['accuracy'])} over {a['points']} points (TP {a['tp']}, FP {a['fp']}, FN {a['fn']}, TN {a['tn']}). "
            f"{a['uncertain_points_not_counted']} points the labeller was unsure of are not counted "
            f"(the grader agreed on {a['uncertain_agreement']}).",
            "",
            "| Check | Passed | Failing cases |",
            "|---|---|---|",
        ]
        for name, d in s["dimensions"].items():
            if d["cases"]:
                failed = ", ".join(d.get("failed", [])) if s["split"] == "dev" else "(not listed)"
                lines.append(f"| {name} | {d['passed']} / {d['cases']} | {failed or '—'} |")
        if s.get("exposure"):
            lines += ["", f"Exposure: {s['exposure']}"]
        lines += _metrics_markdown(s.get("protocol_metrics"))
        lines += ["", "| Kind of answer | Cases | All checks passed |", "|---|---|---|"]
        lines += [f"| {t} | {v['cases']} | {v.get('all_checks_passed', 0)} |" for t, v in s["by_tag"].items()]
        if s["split"] == "dev":
            failing = [c for c in s["cases"] if any(not ch["passed"] for ch in c.get("checks", {}).values())]
            if failing:
                lines += ["", "| Case | Observed | Failed checks |", "|---|---|---|"]
                for c in failing:
                    bad = "; ".join(
                        f"**{k}**: " + " / ".join(v["problems"])
                        for k, v in c["checks"].items()
                        if not v["passed"]
                    )
                    o = c["observed"]
                    lines.append(
                        f"| `{c['id']}` ({', '.join(c['tags'])}) | {o['score']} {o['rating']} | {bad} |"
                    )
        else:
            lines += [
                "",
                "Held-out case details are in the JSON report, not here, so the set isn't read while tuning.",
            ]
        lines.append("")
    return lines


def _rate(m: dict) -> str:
    if not m or not m["n"]:
        return "n/a (0 cases)"
    ci = m["ci95"]
    return f"{m['k']}/{m['n']} = {m['rate']:.0%} (95% CI {ci[0]:.0%}–{ci[1]:.0%})"


def _metrics_markdown(m: dict | None) -> list[str]:
    if not m:
        return []
    names = [k for k in m if k != "per_variant" and m[k]["n"]]
    lines = ["", "| Protocol metric | Value |", "|---|---|"]
    lines += [f"| {k} | {_rate(m[k])} |" for k in names]
    if m.get("per_variant") and len(m["per_variant"]) > 1:
        lines += ["", "| Variant | Cases | Precision | Recall |", "|---|---|---|---|"]
        lines += [
            f"| {v} | {row['cases']} | {_rate(row['precision'])} | {_rate(row['recall'])} |"
            for v, row in m["per_variant"].items()
        ]
    return lines


def _regression_markdown(r: dict) -> list[str]:
    rows = r.get("regression")
    if not rows:
        return []
    lines = [
        "## Known defects (evals/regression.json)",
        "",
        "| Defect | Recorded | Measured now | Cases showing it |",
        "|---|---|---|---|",
    ]
    for d in rows:
        showing = [c["case"] for c in d["cases"] if c["shows_defect"]]
        lines.append(
            f"| {d['id']} | {d['status_recorded']} | {'still shows' if d['still_shows'] else 'not shown'} | {', '.join(showing) or '—'} |"
        )
    return lines + [""]


def _coding_markdown(r: dict) -> list[str]:
    lines: list[str] = []
    rv, h = r.get("review"), r.get("hints")
    if rv and h:
        lines += [
            "## Code review and hints: tuning set",
            "",
            f"{rv['samples']} labelled review samples; hints on {h['problems']} problems (spoiler and relevance rates on the "
            f"{h['labeled_problems']} with labelled terms; code-leak checks on all).",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Schema validity | {_pct(rv['schema_validity'])} |",
            f"| Issue detection (micro) precision / recall / F1 | {_pct(rv['issue_detection_micro']['precision'])} / {_pct(rv['issue_detection_micro']['recall'])} / {_pct(rv['issue_detection_micro']['f1'])} |",
            f"| False alarms on clean code (medium/high issue on a clean sample) | {_pct(rv['false_alarm_rate_on_clean_code'])} of {rv['clean_samples']} |",
            f"| Complexity (Big-O) accuracy | {_pct(rv['complexity_accuracy'])} |",
            f"| Level-1 hint spoiler rate | {_pct(h['level1_spoiler_rate'])} |",
            f"| Level-2 hint relevance | {_pct(h['level2_relevance'])} |",
            f"| Code in level 1–2 hints | {_pct(h['code_leak_rate_levels_1_2'])} |",
            "",
        ]
    for key, title in (
        ("review_holdout", "Held-out set (generalisation)"),
        ("review_medium", "Medium held-out set (newer problems)"),
    ):
        if r.get(key):
            lines += _holdout_section(r[key], title)
    if rv:
        lines += [
            "## Issue detection by category (tuning set)",
            "",
            "| Category | Precision | Recall | F1 | TP | FP | FN |",
            "|---|---|---|---|---|---|---|",
        ]
        for c, mm in rv["issue_detection_by_category"].items():
            lines.append(
                f"| {c} | {_pct(mm['precision'])} | {_pct(mm['recall'])} | {_pct(mm['f1'])} | {mm['tp']} | {mm['fp']} | {mm['fn']} |"
            )
        lines += [
            "",
            "## Disagreements with the labels (tuning set)",
            "",
            "| Sample | Expected | Reviewer said | Big-O expected → reported |",
            "|---|---|---|---|",
        ]
        for d in rv["disagreements"]:
            lines.append(
                f"| `{d['id']}` | {', '.join(d['expected']) or '—'} | {', '.join(d['predicted']) or '—'} | "
                f"{d['time_expected']} → {d['time_predicted']} |"
            )
        lines.append("")
    return lines


def _holdout_section(ho: dict, title: str) -> list[str]:
    mm = ho["issue_detection_micro"]
    rows = [
        f"## {title}",
        "",
        f"{ho['samples']} samples written after the rules were frozen; never used to tune them.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Issue detection (micro) precision / recall / F1 | {_pct(mm['precision'])} / {_pct(mm['recall'])} / {_pct(mm['f1'])} |",
        f"| False alarms on clean code | {_pct(ho['false_alarm_rate_on_clean_code'])} of {ho['clean_samples']} |",
        f"| Complexity (Big-O) accuracy | {_pct(ho['complexity_accuracy'])} |",
        "",
        "| Sample | Expected | Reviewer said | Big-O expected → reported |",
        "|---|---|---|---|",
    ]
    for d in ho["disagreements"]:
        rows.append(
            f"| `{d['id']}` | {', '.join(d['expected']) or '—'} | {', '.join(d['predicted']) or '—'} | "
            f"{d['time_expected']} → {d['time_predicted']} |"
        )
    return rows + [""]


def compare_markdown(c: dict) -> str:
    lines = [f"# Comparison: baseline `{c['baseline_run']}` → candidate `{c['candidate_run']}`", ""]
    if not c["comparable"]:
        return "\n".join(
            lines
            + [
                f"**Not comparable**: these datasets differ between the runs: {', '.join(c['changed_datasets'])}.",
                "",
            ]
        )
    lines += ["## Changed conditions", ""]
    lines += [
        f"- {k}: `{v['baseline']}` → `{v['candidate']}`" for k, v in c["changed_conditions"].items()
    ] or ["- none"]
    lines += ["", "## Metrics (baseline → candidate)", ""]
    for section, values in c["metrics"].items():
        lines.append(
            f"- **{section}**: "
            + ", ".join(f"{k} {v[0]} → {v[1]}" for k, v in values.items() if isinstance(v, list))
        )
    lines += ["", f"## Regressions ({len(c['regressed'])})", ""]
    lines += [f"- {x}" for x in c["regressed"]] or ["- none"]
    lines += ["", f"## Fixed ({len(c['fixed'])})", ""]
    lines += [f"- {x}" for x in c["fixed"]] or ["- none"]
    return "\n".join(lines) + "\n"


SEALED_DIR = EVAL_DIR / "sealed"


def write_report(report: dict, label: str, out: Path = EVAL_DIR / "results") -> Path:
    """Write <label>.json and .md together (each replaced atomically), with the same run id.

    A sealed run's case-level results go to evals/sealed/results/<label>.cases.json instead, and
    the report and markdown keep aggregates only, so reading the report doesn't expose cases."""
    out.mkdir(exist_ok=True)
    if report.get("kind") == "sealed":
        cases_dir = SEALED_DIR / "results"
        cases_dir.mkdir(parents=True, exist_ok=True)
        detail = {"run_id": report["meta"]["run_id"], "career": report.get("career", {})}
        (cases_dir / f"{label}.cases.json").write_text(
            json.dumps(detail, indent=2, ensure_ascii=False) + "\n"
        )
        report = {**report, "career": {k: _aggregate_only(v) for k, v in report.get("career", {}).items()}}
        report["gates"] = [
            {
                **g,
                "failures": [f"{len(g['failures'])} failing (case-level detail sealed)"]
                if g["failures"]
                else [],
            }
            for g in report.get("gates", [])
        ]
        with (SEALED_DIR / "ACCESS.md").open("a", encoding="utf-8") as log:
            log.write(
                f"| {report['finished_at']} | graded | run `{report['meta']['run_id']}` at commit "
                f"`{str(report['meta']['commit'])[:12]}`, rubric {report['meta']['rubric_version']}; case-level results "
                f"written to sealed/results/{label}.cases.json, not opened |\n"
            )
    for suffix, text in (
        (".json", json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
        (".md", to_markdown(report)),
    ):
        tmp = out / f".{label}{suffix}.tmp"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, out / f"{label}{suffix}")
    return out / f"{label}.json"


def _aggregate_only(result: dict) -> dict:
    """A graded set without anything case-level: counts, dimensions, metrics."""
    keep = (
        "dataset",
        "dataset_version",
        "split",
        "track",
        "cases_planned",
        "cases_scored",
        "point_agreement",
        "protocol_metrics",
        "by_tag",
    )
    out = {k: result[k] for k in keep if k in result}
    out["dimensions"] = {
        k: {"cases": v["cases"], "passed": v["passed"]} for k, v in result["dimensions"].items()
    }
    out["case_errors"] = len(result.get("case_errors", []))
    out["cases"] = []
    return out


def report_problems(path: Path) -> list[str]:
    """Why a saved report doesn't belong to the current code and data (empty: it does)."""
    report = json.loads(path.read_text(encoding="utf-8"))
    m = report["meta"]
    out = []
    head = meta.git_state()["commit"]
    if m.get("commit") != head:
        out.append(f"report is from commit {str(m.get('commit'))[:12]}, HEAD is {str(head)[:12]}")
    if m.get("uncommitted_changes"):
        out.append("report was produced with uncommitted changes")
    current = {d["id"]: d["sha256_actual"] for d in meta.datasets()}
    out += [
        f"dataset {d['id']} changed since the run"
        for d in m["datasets"]
        if current.get(d["id"]) != d["sha256_actual"]
    ]
    md = path.with_suffix(".md")
    if md.exists() and m["run_id"] not in md.read_text(encoding="utf-8"):
        out.append(f"{md.name} is from a different run than {path.name}")
    if not report.get("complete"):
        out.append("partial run: " + "; ".join(report.get("incomplete_reasons", [])))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", default="offline", choices=["offline", "anthropic"])
    parser.add_argument("--split", default="all", choices=["all", "dev", "holdout"])
    parser.add_argument("--sections", nargs="+", default=list(SECTIONS), choices=SECTIONS)
    parser.add_argument("--limit", type=int, help="first N cases per set only (marks the run partial)")
    parser.add_argument(
        "--career-grader", help="grade career answers with another grade(): git:<commit> or a file"
    )
    parser.add_argument("--label", help="report name (default: the provider)")
    parser.add_argument("--allow-paid-calls", action="store_true", help="required for --provider anthropic")
    parser.add_argument(
        "--max-calls", type=int, help="stop (and mark the run partial) after this many provider calls"
    )
    parser.add_argument("--price-input-per-mtok", type=float)
    parser.add_argument("--price-output-per-mtok", type=float)
    parser.add_argument("--price-source", help="where the prices came from (recorded with the cost)")
    parser.add_argument(
        "--gate", metavar="REPORT", help="evaluate the release gates on a saved report; exit 1 on failure"
    )
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    parser.add_argument("--check-report", metavar="REPORT")
    args = parser.parse_args()

    if args.check_report:
        problems = report_problems(Path(args.check_report))
        print("\n".join(problems) or "The report belongs to this commit and these datasets, and is complete.")
        raise SystemExit(1 if problems else 0)
    if args.compare:
        b, c = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        result = compare(b, c)
        print(compare_markdown(result))
        raise SystemExit(0 if result["comparable"] and not result["regressed"] else 1)
    if args.gate:
        report = json.loads(Path(args.gate).read_text(encoding="utf-8"))
        gates = evaluate_gates(report)
        for g in gates:
            print(f"{g['status']:>8}  {g['id']}")
            for f in g["failures"]:
                print(f"          - {f}")
        raise SystemExit(1 if any(g["status"] == "failed" for g in gates) else 0)

    prices = None
    if args.provider == "anthropic":
        if not args.allow_paid_calls or args.max_calls is None:
            raise SystemExit("Calls to Claude cost money: pass --allow-paid-calls and a --max-calls budget.")
        if (args.price_input_per_mtok is None) != (args.price_output_per_mtok is None):
            raise SystemExit("Give both prices or neither.")
        if args.price_input_per_mtok is not None:
            prices = {
                "input_per_mtok": args.price_input_per_mtok,
                "output_per_mtok": args.price_output_per_mtok,
                "source": args.price_source or "not stated",
            }
    report = run(
        args.provider,
        split=args.split,
        sections=tuple(args.sections),
        career_grader=load_grader(args.career_grader) if args.career_grader else None,
        limit=args.limit,
        max_calls=args.max_calls,
        prices=prices,
    )
    path = write_report(report, args.label or report["meta"]["provider"])
    print(to_markdown(report))
    print(f"wrote {path} and {path.with_suffix('.md')}")


if __name__ == "__main__":
    main()
