"""Compile and run the repository's own reference solutions against every seeded test case.

Why: test data is only trustworthy if a known-good solution passes all of it. This catches
typos in expected outputs before a learner ever sees a wrong verdict.

Safety: this runs ONLY trusted code that is checked into this repository
(app/seed/reference/*.java). It is a developer and CI tool, not the submission runner, and it
must never be pointed at user-submitted code. See docs/security/threat-model.md.

Usage:  python scripts/verify_reference_solutions.py
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.judge.harness import build_driver, judge_cases  # noqa: E402

PROBLEMS_DIR = BACKEND_DIR / "app" / "seed" / "problems"
REFERENCE_DIR = BACKEND_DIR / "app" / "seed" / "reference"
DEBUGGING_DIR = BACKEND_DIR / "app" / "seed" / "debugging"
REVIEWS_DIR = BACKEND_DIR / "app" / "seed" / "reviews"
TEST_DESIGN_DIR = BACKEND_DIR / "app" / "seed" / "testdesign"
FUZZ_CASES = 200


def java_available() -> bool:
    return shutil.which("javac") is not None and shutil.which("java") is not None


def run_source(problem: dict, source: str, timeout_s: float = 30.0) -> tuple[str | None, list]:
    """Compile `source` as the Solution for `problem` and run every test case through the
    production driver and comparison. Returns (compile error or None, per-test outcomes)."""
    tests = problem["tests"]
    driver = build_driver(problem["signature"], [t["input"] for t in tests])
    with tempfile.TemporaryDirectory(prefix=f"cc-ref-{problem['slug']}-") as tmp:
        work = Path(tmp)
        (work / "Solution.java").write_text(source)
        (work / "Main.java").write_text(driver)
        compiled = subprocess.run(
            ["javac", "-d", str(work), str(work / "Solution.java"), str(work / "Main.java")],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if compiled.returncode != 0:
            return compiled.stderr[:2000], []
        nonce = secrets.token_hex(16)
        ran = subprocess.run(
            ["java", "-cp", str(work), "Main"],
            input=nonce + "\n",
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    return None, judge_cases([t["expected_output"] for t in tests], ran.stdout, nonce)


def _describe(slug: str, tests: list, outcome) -> str:
    t = tests[outcome.index]
    return (
        f"{slug} test #{outcome.index} ({t['visibility']}): input={t['input']} "
        f"expected={t['expected_output']!r} actual={outcome.actual!r} "
        f"exception={outcome.exception!r} missing={outcome.missing}"
    )


def check_problem(problem_file: Path, timeout_s: float = 30.0) -> list[str]:
    """Return a list of human-readable failures (empty means every test passed)."""
    problem = json.loads(problem_file.read_text())
    slug = problem["slug"]
    reference = REFERENCE_DIR / f"{slug}.java"
    if not reference.exists():
        return [f"{slug}: missing reference solution {reference.name}"]
    error, outcomes = run_source(problem, reference.read_text(), timeout_s)
    if error is not None:
        return [f"{slug}: compile error\n{error}"]
    return [_describe(slug, problem["tests"], o) for o in outcomes if not o.passed]


def check_debug_exercise(problem_file: Path, timeout_s: float = 30.0) -> list[str]:
    """A debugging exercise (app/seed/debugging) is sound when:
    - its faulty starter compiles and runs without crashing (a logic defect, not a compile or
      runtime failure), fails exactly the public cases its `lab.reproduction` names, passes the
      other public cases, and fails at least one test overall;
    - its reference repair, and every alternative repair in debugging/alternatives, pass every test.
    Returns human-readable failures (empty means sound)."""
    problem = json.loads(problem_file.read_text())
    slug, tests = problem["slug"], problem["tests"]
    failures = check_problem(problem_file, timeout_s)
    error, outcomes = run_source(problem, problem["starter_code"], timeout_s)
    if error is not None:
        failures.append(
            f"{slug}: the faulty starter doesn't compile (a debugging exercise is about logic)\n{error}"
        )
    else:
        crashed = [o for o in outcomes if o.exception or o.missing]
        failures += [
            f"{slug}: the starter crashes instead of failing: {_describe(slug, tests, o)}" for o in crashed
        ]
        public = {i for i, t in enumerate(tests) if t["visibility"] == "public"}
        failing_public = {o.index for o in outcomes if not o.passed and o.index in public}
        declared = set(problem["lab"]["reproduction"])
        if failing_public != declared:
            failures.append(
                f"{slug}: the starter fails public tests {sorted(failing_public)}, "
                f"but lab.reproduction says {sorted(declared)}"
            )
        if failing_public == public:
            failures.append(f"{slug}: the starter fails every public test; keep a simple case that passes")
    for alternative in sorted((problem_file.parent / "alternatives").glob(f"{slug}.*.java")):
        alt_error, alt_outcomes = run_source(problem, alternative.read_text(), timeout_s)
        if alt_error is not None:
            failures.append(f"{slug}: alternative {alternative.name} doesn't compile\n{alt_error}")
        failures += [
            f"{slug}: alternative {alternative.name}: {_describe(slug, tests, o)}"
            for o in alt_outcomes
            if not o.passed
        ]
    return failures


def _problem_for(slug: str) -> dict | None:
    for path in PROBLEMS_DIR.glob(f"*-{slug}.json"):
        data = json.loads(path.read_text())
        if data.get("slug") == slug:
            return data
    return None


def check_review_exercise(review_file: Path, timeout_s: float = 30.0) -> list[str]:
    """A code-review exercise (app/seed/reviews; docs/CODE_REVIEW_PRACTICE.md) is sound when its
    authored review matches what the code does on the problem's tests:
    - the reviewed code compiles and runs without crashing;
    - the public tests it fails are exactly those its defects cite as evidence, each with the
      result the evidence states; and with no defect, it passes every public and hidden test (an
      exercise with no defect must really have none);
    - with a defect, it fails at least one test, and `repaired_code` passes every test.
    Returns human-readable failures (empty means sound)."""
    review = json.loads(review_file.read_text())
    slug = review["slug"]
    problem = _problem_for(review["problem"])
    if problem is None:
        return [f"{slug}: no coding problem {review['problem']!r}"]
    tests = problem["tests"]
    failures: list[str] = []
    error, outcomes = run_source(problem, review["code"], timeout_s)
    if error is not None:
        return [f"{slug}: the reviewed code doesn't compile\n{error}"]
    # An expected exception (a test that wants IllegalArgumentException) passes; any other is a crash.
    crashed = [o for o in outcomes if not o.passed and (o.exception or o.missing)]
    failures += [f"{slug}: the reviewed code crashes: {_describe(slug, tests, o)}" for o in crashed]
    public = [i for i, t in enumerate(tests) if t["visibility"] == "public"]
    position = {index: n for n, index in enumerate(public, 1)}  # test index -> public position
    failing_public = {position[o.index]: o for o in outcomes if not o.passed and o.index in position}
    defects = [f for f in review["findings"] if f["kind"] == "defect"]
    cited = {e["public_test"]: e for f in defects for e in f.get("evidence", [])}
    if set(failing_public) != set(cited):
        failures.append(
            f"{slug}: the code fails public tests {sorted(failing_public)}, "
            f"but the defects cite {sorted(cited)}"
        )
    for pos, e in cited.items():
        o = failing_public.get(pos)
        if o is not None and o.actual != e["actual"]:
            failures.append(
                f"{slug}: public test {pos} returns {o.actual!r}, but the evidence says {e['actual']!r}"
            )
    failed_any = [o for o in outcomes if not o.passed]
    if not defects and failed_any:
        failures += [
            f"{slug}: has no defect in its review but fails: {_describe(slug, tests, o)}" for o in failed_any
        ]
    if defects:
        if not failed_any:
            failures.append(f"{slug}: its review has a defect, but the code passes every test")
        repaired = review.get("repaired_code") or ""
        fix_error, fix_outcomes = run_source(problem, repaired, timeout_s)
        if fix_error is not None:
            failures.append(f"{slug}: repaired_code doesn't compile\n{fix_error}")
        failures += [
            f"{slug}: repaired_code fails: {_describe(slug, tests, o)}" for o in fix_outcomes if not o.passed
        ]
    return failures


def run_files(files: dict[str, str], timeout_s: float = 60.0) -> tuple[str | None, str, str, bool]:
    """Compile and run Main with the local JDK. Returns (compile error, stdout, nonce, timed out)."""
    nonce = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="cc-td-") as tmp:
        work = Path(tmp)
        for name, text in files.items():
            (work / name).write_text(text)
        compiled = subprocess.run(
            ["javac", "-d", str(work), *[str(work / n) for n in files]],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if compiled.returncode != 0:
            return compiled.stderr[:2000], "", nonce, False
        try:
            ran = subprocess.run(
                ["java", "-cp", str(work), "Main"],
                input=nonce + "\n",
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None, "", nonce, True
    return None, ran.stdout, nonce, False


def _fuzz_inputs(ex, count: int) -> list[dict]:
    """Inputs within the exercise's limits: the edges (empty, one value, full length, extreme
    values) and seeded random ones, so the check is reproducible."""
    import random

    rng = random.Random(f"{ex.slug}:{ex.version}")
    lim = ex.limits
    array_name = ex.params[0]["name"]
    ints = [p["name"] for p in ex.params[1:]]

    def one(length: int, lo: int, hi: int) -> dict:
        case = {array_name: [rng.randint(lo, hi) for _ in range(length)]}
        for name in ints:
            case[name] = rng.randint(lo, hi)
        return case

    small = (-5, 5)  # small values make repeats and bound hits likely
    inputs = [one(0, *small), one(1, *small), one(lim.max_length, lim.min_value, lim.max_value)]
    inputs.append({array_name: [lim.min_value, lim.max_value], **dict.fromkeys(ints, lim.max_value)})
    while len(inputs) < count:
        span = small if rng.random() < 0.7 else (lim.min_value, lim.max_value)
        inputs.append(one(rng.randint(0, lim.max_length), *span))
    return inputs


def check_test_design_exercise(path: Path, timeout_s: float = 60.0) -> list[str]:
    """A test-design exercise (app/seed/testdesign; docs/TEST_DESIGN.md) is sound when, run with a
    real JDK through the same multi-implementation driver the judge uses:
    - the reference and every faulty version compile and finish on every input below (no hang);
    - the reference returns each example's expected output, and never throws on the examples, the
      witnesses or FUZZ_CASES seeded inputs within the limits (so it can decide any valid case);
    - each faulty version differs from the reference on its own witness case (its defect shows);
    - the examples don't already tell every faulty version apart (something is left to find).
    Expected outputs come only from running the reference. Returns failures (empty means sound)."""
    from app.services.judge.harness import outputs_match, parse_driver_output
    from app.testdesign import build_sources, case_errors, parse

    ex = parse(json.loads(path.read_text()))
    slug = ex.slug
    examples = [e["input"] for e in ex.examples]
    witnesses = [v.witness for v in ex.variants]
    inputs = examples + witnesses + _fuzz_inputs(ex, FUZZ_CASES)
    dummy = True if ex.returns == "boolean" else 0
    failures = [
        f"{slug}: input {case} is outside the limits: {errs}"
        for case in examples + witnesses
        if (errs := case_errors(ex, case, dummy))
    ]
    files, n_impl = build_sources(ex, inputs)
    error, stdout, nonce, timed_out = run_files(files, timeout_s)
    if error is not None:
        return [*failures, f"{slug}: the reference or a faulty version doesn't compile\n{error}"]
    if timed_out:
        return [*failures, f"{slug}: an implementation didn't finish within {timeout_s} s (a hang?)"]
    out = parse_driver_output(stdout, nonce)
    n = len(inputs)
    names = ["reference"] + [v.id for v in ex.variants]

    def result(impl: int, i: int) -> dict | None:
        return out.get(impl * n + i)

    for k, name in enumerate(names):
        missing = [i for i in range(n) if result(k, i) is None]
        if missing:
            failures.append(
                f"{slug}: {name} gave no result for {len(missing)} inputs (first: {inputs[missing[0]]})"
            )
    for i, case in enumerate(inputs):
        ref = result(0, i)
        if ref is not None and not ref.get("ok"):
            failures.append(f"{slug}: the reference throws {ref.get('exception')} on {case}")
    for i, e in enumerate(ex.examples):
        ref = result(0, i)
        if ref is not None and ref.get("ok") and not outputs_match(e["expected"], ref.get("output")):
            failures.append(
                f"{slug}: example {i + 1} expects {e['expected']!r}, but the reference returns {ref.get('output')!r}"
            )

    def differs(k: int, i: int) -> bool:
        a, b = result(0, i), result(k, i)
        if a is None or b is None:
            return False
        if bool(a.get("ok")) != bool(b.get("ok")):
            return True
        if a.get("ok"):
            return not outputs_match(a.get("output"), b.get("output"))
        return a.get("exception") != b.get("exception")

    for k, v in enumerate(ex.variants, start=1):
        if not differs(k, len(examples) + k - 1):
            failures.append(
                f"{slug}: faulty version {v.id} gives the reference's answer on its own witness {v.witness}"
            )
    if all(any(differs(k, i) for i in range(len(examples))) for k in range(1, n_impl)):
        failures.append(
            f"{slug}: the examples already tell every faulty version apart; nothing is left to find"
        )
    return failures


_BATCH_RUNNER = r"""
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.*;

public final class BatchRunner {
    public static void main(String[] args) throws Exception {
        String nonce = args[0];
        Path outDir = Paths.get(args[1]);
        PrintStream realOut = System.out;
        InputStream realIn = System.in;
        ExecutorService pool = Executors.newCachedThreadPool(r -> { Thread t = new Thread(r); t.setDaemon(true); return t; });
        for (int i = 2; i < args.length; i++) {
            String pkg = args[i];
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            System.setIn(new ByteArrayInputStream((nonce + "\n").getBytes()));
            System.setOut(new PrintStream(buf, true));
            Future<?> f = pool.submit(() -> {
                Class.forName(pkg + ".Main").getMethod("main", String[].class).invoke(null, (Object) new String[0]);
                return null;
            });
            String status = "ok";
            try { f.get(20, TimeUnit.SECONDS); }
            catch (TimeoutException e) { status = "timeout"; f.cancel(true); }
            catch (ExecutionException e) { status = "crash " + e.getCause(); }
            System.setOut(realOut);
            System.setIn(realIn);
            Files.write(outDir.resolve(pkg + ".txt"), buf.toByteArray());
            realOut.println(pkg + " " + status);
        }
        System.exit(0);
    }
}
"""


def check_all(
    problem_files: list[Path], reference_dir: Path | None = None, timeout_s: float = 600.0
) -> dict[str, list[str]]:
    """Check many problems at once: one javac and one JVM for all of them, instead of one each.

    Each problem's Solution and generated Main go into their own package (p0, p1, ...), so the
    fixed class names don't collide. Returns {slug: failures}; an empty list means it passed.
    """
    reference_dir = reference_dir or REFERENCE_DIR
    problems = [json.loads(f.read_text()) for f in problem_files]
    results: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="cc-ref-batch-") as tmp:
        work = Path(tmp)
        src, classes, outputs = work / "src", work / "classes", work / "out"
        for d in (src, classes, outputs):
            d.mkdir()
        packages: dict[str, dict] = {}
        for i, problem in enumerate(problems):
            slug = problem["slug"]
            ref = reference_dir / f"{slug}.java"
            if not ref.exists():
                results[slug] = [f"{slug}: missing reference solution {ref.name}"]
                continue
            pkg = f"p{i}"
            (src / pkg).mkdir()
            (src / pkg / "Solution.java").write_text(f"package {pkg};\n" + ref.read_text())
            driver = build_driver(problem["signature"], [t["input"] for t in problem["tests"]])
            (src / pkg / "Main.java").write_text(f"package {pkg};\n" + driver)
            packages[pkg] = problem
        (src / "BatchRunner.java").write_text(_BATCH_RUNNER)
        sources = [str(p) for p in src.rglob("*.java")]
        (work / "sources.txt").write_text("\n".join(sources))
        compiled = subprocess.run(
            ["javac", "-nowarn", "-d", str(classes), f"@{work / 'sources.txt'}"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if compiled.returncode != 0:
            # Attribute compile errors to the problems whose files are named in the output.
            for pkg, problem in packages.items():
                if f"/{pkg}/" in compiled.stderr:
                    results[problem["slug"]] = [f"{problem['slug']}: compile error\n{compiled.stderr[:2000]}"]
            if not results:
                raise RuntimeError(compiled.stderr[:4000])
            return {
                **{
                    p["slug"]: results.get(p["slug"], ["not run: another problem failed to compile"])
                    for p in problems
                }
            }
        nonce = secrets.token_hex(16)
        ran = subprocess.run(
            ["java", "-cp", str(classes), "BatchRunner", nonce, str(outputs), *packages],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        statuses = dict(line.split(" ", 1) for line in ran.stdout.splitlines() if " " in line)
        for pkg, problem in packages.items():
            slug, tests = problem["slug"], problem["tests"]
            if statuses.get(pkg, "missing") != "ok":
                results[slug] = [f"{slug}: {statuses.get(pkg, 'did not run')}"]
                continue
            stdout = (outputs / f"{pkg}.txt").read_text()
            failures = []
            for outcome in judge_cases([t["expected_output"] for t in tests], stdout, nonce):
                if not outcome.passed:
                    t = tests[outcome.index]
                    failures.append(
                        f"{slug} test #{outcome.index} ({t['visibility']}): input={t['input']} "
                        f"expected={t['expected_output']!r} actual={outcome.actual!r} "
                        f"exception={outcome.exception!r} missing={outcome.missing}"
                    )
            results[slug] = failures
    return results


def main() -> int:
    if not java_available():
        print("javac/java not found on PATH; install a JDK (17+) to run this check.")
        return 2
    files = sorted(PROBLEMS_DIR.glob("*.json"))
    all_failures: list[str] = []
    for slug, failures in check_all(files).items():
        print(f"{slug:40s} {'ok' if not failures else f'{len(failures)} failure(s)'}")
        all_failures.extend(failures)
    if all_failures:
        print("\n".join(all_failures))
        return 1
    print(f"All {len(files)} reference solutions pass every test case.")
    exercises = sorted(DEBUGGING_DIR.glob("*.json"))
    for path in exercises:
        failures = check_debug_exercise(path)
        print(f"{path.stem:40s} {'ok' if not failures else f'{len(failures)} failure(s)'}")
        all_failures.extend(failures)
    if all_failures:
        print("\n".join(all_failures))
        return 1
    print(
        f"All {len(exercises)} debugging exercises: each starter fails exactly its reproduction cases; repairs pass."
    )
    reviews = sorted(REVIEWS_DIR.glob("*.json"))
    for path in reviews:
        failures = check_review_exercise(path)
        print(f"{path.stem:40s} {'ok' if not failures else f'{len(failures)} failure(s)'}")
        all_failures.extend(failures)
    if all_failures:
        print("\n".join(all_failures))
        return 1
    print(
        f"All {len(reviews)} review exercises: each authored review matches what the code does on the tests."
    )
    designs = sorted(TEST_DESIGN_DIR.glob("*.json"))
    for path in designs:
        failures = check_test_design_exercise(path)
        print(f"{path.stem:40s} {'ok' if not failures else f'{len(failures)} failure(s)'}")
        all_failures.extend(failures)
    if all_failures:
        print("\n".join(all_failures))
        return 1
    print(
        f"All {len(designs)} test design exercises: examples match the reference, each faulty version shows its defect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
