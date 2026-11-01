"""Guards for the migration files themselves."""

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def test_migrations_never_reference_application_code():
    """A migration must keep working after the app's models change, so it may only use
    alembic + sqlalchemy. (Regression: autogenerate once emitted `app.models.UTCDateTime`
    without an import, which would have crashed `alembic upgrade` on deploy.)"""
    offenders = []
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text()
        if re.search(r"^\s*(from|import)\s+app\b", text, re.M) or re.search(r"\bapp\.\w", text):
            offenders.append(path.name)
    assert offenders == []


def test_migration_chain_is_linear():
    revisions, downs = {}, []
    for path in VERSIONS.glob("*.py"):
        text = path.read_text()
        rev = re.search(r'^revision: str = "(\w+)"', text, re.M).group(1)
        down = re.search(r"^down_revision: [^=]+= (None|\"(\w+)\")", text, re.M)
        revisions[rev] = path.name
        downs.append(down.group(2))
    roots = [d for d in downs if d is None]
    assert len(roots) == 1, "exactly one initial migration"
    assert len(set(d for d in downs if d)) == len(downs) - 1, "no branches: each revision has one child"
