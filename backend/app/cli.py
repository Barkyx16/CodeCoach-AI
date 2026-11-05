"""Operational commands.

python -m app.cli seed        # upsert the curated problem library
python -m app.cli openapi     # print the OpenAPI schema (JSON) to stdout
python -m app.cli prune-guests [--days N]   # delete guest accounts inactive for N days
                                            # (default GUEST_RETENTION_DAYS)
python -m app.cli judge-check # prove the configured code judge works, end to end
python -m app.cli check-export FILE.json  # read-only check of a version 2 export's ids and links
python -m app.cli grant-admin EMAIL    # let a registered account triage content reports
python -m app.cli revoke-admin EMAIL
python -m app.cli check-answers [--limit-ids N]
                              # read-only checks of saved career answers: request keys, revision
                              # links, score eligibility (reason codes and ids, never answer text)
python -m app.cli validate-content [--run-reference] [--record]
                              # content quality gates; --run-reference compiles and runs the
                              # trusted reference solutions (local JDK); --record stores results
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import get_settings
from app.db.seed import seed_problems
from app.db.session import make_engine, make_session_factory

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "seed":
        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            print(f"Seeded {seed_problems(session)} problems")
        return 0
    if command == "openapi":
        from app.main import create_app

        OPENAPI_PATH.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")
        print(f"Wrote {OPENAPI_PATH}")
        return 0
    if command == "prune-guests":
        from app.services.retention import prune_inactive_guests

        settings = get_settings()
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else settings.guest_retention_days
        engine = make_engine(settings.database_url)
        with make_session_factory(engine)() as session:
            print(f"Deleted {prune_inactive_guests(session, days)} guest accounts inactive for {days}+ days")
        return 0
    if command == "check-export":
        # Read-only: checks a version 2 export's ids and links; changes nothing anywhere.
        from app.services.export_v2 import validate_export

        if len(argv) < 3:
            print("usage: python -m app.cli check-export FILE.json")
            return 2
        issues = validate_export(json.loads(Path(argv[2]).read_text(encoding="utf-8")))
        for i in issues:
            print(f"{i['rule']}: {i['path']}: {i['detail']}")
        print("No problems found." if not issues else f"{len(issues)} problem(s) found.")
        return 1 if issues else 0
    if command == "judge-check":
        from app.services.judge.check import judge_check

        return judge_check(get_settings())
    if command in ("grant-admin", "revoke-admin"):
        from sqlalchemy import func, select

        from app.models import User

        if len(argv) < 3:
            print(f"usage: python -m app.cli {command} EMAIL")
            return 1
        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            user = session.scalar(select(User).where(func.lower(User.email) == argv[2].strip().lower()))
            if user is None or user.is_guest:
                print("No registered account has that email.")
                return 1
            user.is_admin = command == "grant-admin"
            session.commit()
            print(f"{user.email}: admin {'granted' if user.is_admin else 'revoked'}")
        return 0
    if command == "check-answers":
        from app.services.answer_invariants import check

        limit = int(argv[argv.index("--limit-ids") + 1]) if "--limit-ids" in argv else 20
        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            checked = check(session)
        print(json.dumps(checked.summary(limit), indent=2, default=str))
        return 0 if checked.ok else 1
    if command == "validate-content":
        from app.content.validate import run

        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            report = run(session, run_reference="--run-reference" in argv, record="--record" in argv)
        for line in report.errors:
            print(f"ERROR   {line}")
        for line in report.warnings:
            print(f"warning {line}")
        counts = ", ".join(f"{n} {k}" for k, n in report.counts.items())
        ran = f"; reference solutions run for {len(report.checks)} problems" if report.checks else ""
        print(f"Checked {counts}{ran}: {len(report.errors)} errors, {len(report.warnings)} warnings.")
        print("This is automated validation, not expert review.")
        return 0 if report.ok else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
