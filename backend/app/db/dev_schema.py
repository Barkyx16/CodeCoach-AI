"""Development convenience: bring a database an older run created up to the current tables.

`Base.metadata.create_all` (the `auto_migrate` startup step, for local runs) creates missing
tables but never touches an existing one, so a database made by an earlier version of the app
lacks columns added since, and every query that reads them fails ("no such column"). This adds
those columns when that's safe: only columns that are nullable or have a server default (every
additive migration here is one), with `ALTER TABLE ... ADD COLUMN`. Nothing is dropped, renamed
or rewritten; anything it can't add is logged and left for `alembic upgrade head`. Production
runs the real migrations and doesn't use this.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, MetaData, inspect
from sqlalchemy.schema import CreateColumn, CreateIndex

logger = logging.getLogger("codecoach.app")


def add_missing_columns(engine: Engine, metadata: MetaData) -> list[str]:
    """Adds the safe missing columns (and plain indexes on them); returns "table.column" for each."""
    added: list[str] = []
    existing_tables = set(inspect(engine).get_table_names())
    preparer = engine.dialect.identifier_preparer
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all made it whole
            have = {c["name"] for c in inspect(conn).get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                if not col.nullable and col.server_default is None:
                    logger.warning(
                        "dev schema: %s.%s is missing and can't be added safely; run `alembic upgrade head`",
                        table.name,
                        col.name,
                    )
                    continue
                # The column exactly as create_all would write it (type, quoted default, NOT NULL).
                ddl = str(CreateColumn(col).compile(dialect=engine.dialect))
                conn.exec_driver_sql(f"ALTER TABLE {preparer.format_table(table)} ADD COLUMN {ddl}")
                added.append(f"{table.name}.{col.name}")
            have_indexes = {i["name"] for i in inspect(conn).get_indexes(table.name)}
            for index in table.indexes:
                if index.name not in have_indexes and not index.unique:
                    conn.execute(CreateIndex(index))
    if added:
        logger.info(
            "dev schema: added %d column(s) an older run didn't have: %s", len(added), ", ".join(added)
        )
    return added
