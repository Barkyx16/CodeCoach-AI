"""Career tracks: the jobs people can practice interviews for.

The catalog is code, not database rows: it changes with the product, it's reviewed in pull
requests like the coding problems, and every question is generated from it deterministically, so
a question's id always means the same question.
"""

from __future__ import annotations

from app.careers import jobs_business, jobs_edu_trades_ops, jobs_people_public_creative, jobs_tech_health
from app.careers.profiles import JobProfile

DEFAULT_TRACK = "software-engineer"

_ALL: list[JobProfile] = [
    *jobs_tech_health.JOBS,
    *jobs_business.JOBS,
    *jobs_edu_trades_ops.JOBS,
    *jobs_people_public_creative.JOBS,
]

CATALOG: dict[str, JobProfile] = {p.slug: p for p in _ALL}
if len(CATALOG) != len(_ALL):  # pragma: no cover - guarded by tests too
    raise RuntimeError("duplicate career slug in the catalog")

# Categories in the order they appear in pickers.
CATEGORIES: list[str] = list(dict.fromkeys(p.category for p in _ALL))


def get_profile(slug: str) -> JobProfile | None:
    return CATALOG.get(slug)


def is_track(slug: str | None) -> bool:
    return slug is not None and slug in CATALOG
