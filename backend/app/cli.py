"""Operational commands.

python -m app.cli seed        # upsert the curated problem library
python -m app.cli openapi     # print the OpenAPI schema (JSON) to stdout
python -m app.cli prune-guests [--days N]   # delete guest accounts inactive for N days
                                            # (default GUEST_RETENTION_DAYS)
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
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
