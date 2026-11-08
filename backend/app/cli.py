"""Operational commands.

python -m app.cli seed        # upsert the curated problem library
python -m app.cli openapi     # print the OpenAPI schema (JSON) to stdout
python -m app.cli prune-guests [--days N]   # delete guest accounts inactive for N days
                                            # (default GUEST_RETENTION_DAYS)
python -m app.cli judge-check # prove the configured code judge works, end to end
python -m app.cli housekeeping  # retry due emails and run every housekeeping step once, now
python -m app.cli check-email [--connect] [--send-test ADDRESS]
                              # email settings (names and presence only); --connect signs in to the
                              # mail server without sending; --send-test sends ONE test email
python -m app.cli email-status [--recent N] [--job ID] [--message-id ID] [--account EMAIL]
                              # the outbox, redacted: statuses, attempts, error classes, Message-IDs
python -m app.cli email-retry --failed [--hours N]
                              # after an outage: retry failed verification emails (default 24 h)
python -m app.cli check-export FILE.json  # read-only check of a version 2 export's ids and links
python -m app.cli preflight [--connect-email] [--backup-manifest FILE] [--json]
                              # launch checks for THIS environment: ready / blocked / optional /
                              # unverified, each with its reason (docs/LAUNCH.md); exit 1 if blocked
python -m app.cli check-rls [--strict]
                              # is PostgreSQL row-level security in force for this connection?
                              # --strict also fails if this role owns tables or can create them
python -m app.cli grant-app-role ROLE  # as the table owner, after migrating: let the ordinary app
                                       # role read and write rows (and nothing more)
python -m app.cli backup-database --out DIR --recipients FILE [--name NAME]
                              # encrypted full-database backup + manifest (docs/BACKUP.md); a
                              # --name backup (e.g. before an upgrade) is never pruned
python -m app.cli restore-database DUMP.age --identity FILE
                              # into RESTORE_DATABASE_URL, a separate EMPTY database; never the live one
python -m app.cli prune-backups --dir DIR [--keep-daily 7] [--keep-weekly 4] [--keep-monthly 3]
                              [--keep-within-hours 24] [--apply]
                              # which backups to keep (all from the 24 h before the newest, and the
                              # newest of each of the last N days, weeks, months that have one);
                              # a dry run unless --apply
python -m app.cli check-backups --dir DIR [--max-age-hours 26] [--all]
                              # is the newest backup recent and intact (hash vs manifest)? exit 1 if
                              # not, for a scheduler's alert; decrypts nothing
python -m app.cli copy-database --from SQLITE_URL [--apply]
                              # optional: copy a development database into the freshly migrated
                              # DATABASE_URL; a dry run unless --apply (docs/STORAGE.md)
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
    if command == "check-email":
        from app.services.email import check_email

        send_to = argv[argv.index("--send-test") + 1] if "--send-test" in argv else None
        return check_email(get_settings(), connect="--connect" in argv, send_to=send_to)
    if command == "email-status":
        from app.services.email_ops import status_report

        def opt(name: str) -> str | None:
            return argv[argv.index(name) + 1] if name in argv else None

        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            outbox_report = status_report(
                session,
                job_id=opt("--job"),
                message_id=opt("--message-id"),
                account_email=opt("--account"),
                limit=int(opt("--recent") or 20),
            )
        print(
            "counts: "
            + (", ".join(f"{k} {v}" for k, v in sorted(outbox_report["counts"].items())) or "no jobs")
        )
        for job in outbox_report["jobs"]:
            print(
                f"{job['created_at'][:19]}  {job['kind']:<22} {job['status']:<9} attempts={job['attempts']} "
                f"to=*@{job['to_domain']} account={job['account']} job={job['job']}"
                + (f" error={job['last_error']}" if job["last_error"] else "")
                + (f" message_id={job['message_id']}" if job["message_id"] else "")
                + (f" next={job['next_attempt_at'][:19]}" if job["next_attempt_at"] else "")
            )
        print("accepted = the mail server took it; delivery to the inbox isn't known (docs/EMAIL.md).")
        return 0
    if command == "email-retry":
        from datetime import timedelta

        from app.services.email_ops import requeue_failed

        if "--failed" not in argv:
            print("usage: python -m app.cli email-retry --failed [--hours N]")
            return 2
        hours = float(argv[argv.index("--hours") + 1]) if "--hours" in argv else 24.0
        engine = make_engine(get_settings().database_url)
        with make_session_factory(engine)() as session:
            done = requeue_failed(session, within=timedelta(hours=hours))
        print(f"Requeued {done['requeued']} failed verification emails from the last {hours:g} h.")
        if done["not_resendable"]:
            print(
                f"{done['not_resendable']} failed change notices can't be resent (their addresses were cleared)."
            )
        print(
            "They're sent by the next outbox pass (the API's jobs thread, or `python -m app.cli housekeeping`)."
        )
        return 0
    if command == "housekeeping":
        from app.jobs import housekeeping
        from app.services import outbox
        from app.services.email import build_email_sender

        settings = get_settings()
        factory = make_session_factory(make_engine(settings.database_url))
        done = {
            f"emails_{k}": v for k, v in outbox.drain(factory, settings, build_email_sender(settings)).items()
        }
        done |= housekeeping(factory, settings, daily=True)
        print(json.dumps(done, indent=2))
        return 0
    if command == "preflight":
        from app.services.preflight import BLOCKED, render, run_preflight

        manifest = Path(argv[argv.index("--backup-manifest") + 1]) if "--backup-manifest" in argv else None
        checks = run_preflight(
            get_settings(), connect_email="--connect-email" in argv, backup_manifest=manifest
        )
        print(render(checks, as_json="--json" in argv))
        return 1 if any(c.status == BLOCKED for c in checks) else 0
    if command == "check-rls":
        from app.db.rls import rls_status
        from app.db.roles import engine_role_report, least_privilege_problems

        engine = make_engine(get_settings().database_url)
        status = rls_status(engine)
        if not status.get("supported"):
            print(json.dumps(status, indent=2))
            print("SQLite: no row-level security (the application's owner checks still apply).")
            return 0
        role_attrs = engine_role_report(engine) or {}
        print(json.dumps({**status, "role_attributes": role_attrs}, indent=2))
        enforced = not status["role_bypasses_rls"] and not status["missing"]
        print("Row-level security is enforced." if enforced else "Row-level security is NOT enforced.")
        problems = least_privilege_problems(role_attrs)
        for problem in problems:
            print(f"{'FAIL' if '--strict' in argv else 'note'}: role {role_attrs['role']} {problem}")
        if not problems:
            print(
                f"Role {role_attrs['role']} owns nothing and can't create objects: a least-privilege app role."
            )
        return 0 if enforced and not (problems and "--strict" in argv) else 1
    if command == "grant-app-role":
        from app.db.roles import apply_grants

        if len(argv) < 3:
            print("usage: python -m app.cli grant-app-role ROLE   (connected as the table owner)")
            return 2
        engine = make_engine(get_settings().database_url)
        if engine.dialect.name != "postgresql":
            print("SQLite has no roles: nothing to grant.")
            return 0
        try:
            with engine.begin() as conn:
                apply_grants(conn, argv[2])
        except ValueError as exc:
            print(f"Not granted: {exc}")
            return 1
        print(f"Granted row access (no ownership, no DDL, read-only migration ledger) to {argv[2]}.")
        return 0
    if command == "backup-database":
        from app.db.backup import BackupError, backup

        if "--out" not in argv or "--recipients" not in argv:
            print(
                "usage: python -m app.cli backup-database --out DIR --recipients FILE [--name NAME]"
                "   (age public keys)"
            )
            return 2
        import re

        backup_name = argv[argv.index("--name") + 1] if "--name" in argv else None
        if backup_name is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", backup_name):
            print("--name: letters, digits, '.', '_' and '-' only (up to 80), e.g. pre-upgrade-20261108")
            return 2
        try:
            made = backup(
                get_settings().database_url,
                Path(argv[argv.index("--out") + 1]),
                Path(argv[argv.index("--recipients") + 1]),
                name=backup_name,
            )
        except BackupError as exc:
            print(f"Backup failed: {exc}")
            return 1
        rows = sum(made.manifest_data["tables"].values())
        print(
            f"Backup written: {made.dump.name} ({made.dump.stat().st_size} bytes, encrypted) and {made.manifest.name}"
        )
        print(
            f"{len(made.manifest_data['tables'])} tables, {rows} rows, schema {made.manifest_data['schema_revision']}"
        )
        print(f"Took {made.seconds:.2f} s. Not proof of recovery: rehearse a restore (docs/BACKUP.md).")
        return 0
    if command == "restore-database":
        import os

        from app.db.backup import BackupError, restore

        restore_target = os.environ.get("RESTORE_DATABASE_URL")
        if len(argv) < 3 or "--identity" not in argv or not restore_target:
            print(
                "usage: RESTORE_DATABASE_URL=... python -m app.cli restore-database DUMP.age --identity FILE"
            )
            print("(RESTORE_DATABASE_URL: a separate, empty database, connected as the table owner)")
            return 2
        try:
            restored = restore(
                Path(argv[2]),
                Path(argv[argv.index("--identity") + 1]),
                restore_target,
                live_url=os.environ.get("DATABASE_URL"),
            )
        except BackupError as exc:
            print(f"Not restored: {exc}")
            return 1
        print(
            f"Restored {restored.tables} tables, {restored.rows} rows; counts and row-level security policies match."
        )
        print("Timings: " + ", ".join(f"{k} {v:.2f} s" for k, v in restored.timings.items()))
        print(f"Schema: {restored.schema}.")
        for note in restored.notes:
            print(f"Next: {note}")
        print("Next: start the app against it and check sign-in (docs/BACKUP.md).")
        return 0
    if command == "prune-backups":
        from datetime import timedelta

        from app.db.backup_store import prune

        if "--dir" not in argv:
            print(
                "usage: python -m app.cli prune-backups --dir DIR [--keep-daily 7] [--keep-weekly 4]"
                " [--keep-monthly 3] [--keep-within-hours 24] [--apply]"
            )
            return 2

        def keep(flag: str, default: int) -> int:
            return int(argv[argv.index(flag) + 1]) if flag in argv else default

        apply = "--apply" in argv
        try:
            prune_plan = prune(
                Path(argv[argv.index("--dir") + 1]),
                keep("--keep-daily", 7),
                keep("--keep-weekly", 4),
                keep("--keep-monthly", 3),
                timedelta(hours=float(argv[argv.index("--keep-within-hours") + 1]))
                if "--keep-within-hours" in argv
                else timedelta(hours=24),
                apply=apply,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Not pruned: {exc}")
            return 2
        for kept, why in sorted(prune_plan.keep.items(), key=lambda kv: kv[0].stamp, reverse=True):
            print(f"keep    {kept.name}  ({', '.join(why)})")
        for gone in prune_plan.delete:
            print(f"{'deleted' if apply else 'delete '} {gone.name}")
        for half in prune_plan.incomplete:
            print(f"left    {half.name}  (half a pair: not deleted; check it by hand)")
        for path in prune_plan.other:
            print(f"left    {path.name}  (not a backup this command made)")
        verb = "Deleted" if apply else "Would delete"
        print(
            f"Kept {len(prune_plan.keep)}. {verb} {len(prune_plan.delete)}.{'' if apply else ' Dry run: pass --apply.'}"
        )
        return 0
    if command == "check-backups":
        from datetime import timedelta

        from app.db.backup_store import check as check_backups

        if "--dir" not in argv:
            print("usage: python -m app.cli check-backups --dir DIR [--max-age-hours 26] [--all]")
            return 2
        hours = float(argv[argv.index("--max-age-hours") + 1]) if "--max-age-hours" in argv else 26.0
        try:
            backup_health = check_backups(
                Path(argv[argv.index("--dir") + 1]), timedelta(hours=hours), verify_all="--all" in argv
            )
        except FileNotFoundError as exc:
            print(f"FAIL  {exc}")
            return 1
        for note in backup_health.notes:
            print(f"note  {note}")
        for problem in backup_health.problems:
            print(f"FAIL  {problem}")
        if backup_health.ok:
            print(
                "OK    the newest backup is recent and matches its manifest."
                " Not proof of recovery: rehearse a restore (docs/BACKUP.md)."
            )
        return 0 if backup_health.ok else 1
    if command == "copy-database":
        import os

        from sqlalchemy import create_engine

        from app.db.copy import SKIPPED, copy, plan

        source_url = (
            argv[argv.index("--from") + 1] if "--from" in argv else os.environ.get("SOURCE_DATABASE_URL")
        )
        if not source_url:
            print("usage: python -m app.cli copy-database --from sqlite:///path/to/codecoach.db [--apply]")
            print("(the target is DATABASE_URL; for a PostgreSQL source, set SOURCE_DATABASE_URL instead)")
            return 2
        source, target = create_engine(source_url), make_engine(get_settings().database_url)
        copy_plan = plan(source, target)
        print(
            f"From {source.dialect.name} ({source.url.database}) to {target.dialect.name} ({target.url.database})."
        )
        for problem in copy_plan.problems:
            print(f"refused: {problem}")
        if not copy_plan.ok:
            return 1
        for name, rows in copy_plan.counts.items():
            if rows:
                print(f"  copy {rows:>7}  {name}")
        for name, rows in copy_plan.skipped.items():
            if rows:
                print(f"  skip {rows:>7}  {name} ({SKIPPED[name]})")
        if "--apply" not in argv:
            print("Dry run: nothing was written. Re-run with --apply to copy (the source is never changed).")
            return 0
        copied = copy(source, target)
        print(f"Copied {sum(copied.values())} rows in one transaction; every table's count matched.")
        print(
            "Next: python -m app.cli seed  (refreshes the problem library), then grant-app-role if you use one."
        )
        return 0
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
