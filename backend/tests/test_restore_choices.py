"""Names you listed and suggestions you dismissed come back from a backup (Volume 16, prompt 4;
docs/BACKUP_FORMAT.md, docs/PRIVACY.md): the preview counts each (new, already here in any letter
case or by the same key, over the list's limit, no longer offered); restoring adds only what's new;
undoing takes back only what that restore added, keeping a name renamed or a suggestion offered again
since. A name is never in a log, a trace or the restore's own record (only counts and digests). A
dismissal whose suggestion no longer exists is left out with the reason. Another account's are never
read or written. Synthetic data only."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.models import DismissedSuggestion, ImportBatch, ImportedRecord, ListedName
from app.services import listed_names
from tests.test_dismissals import KEY, dismiss, listed
from tests.test_dismissals import URL as DISMISSALS
from tests.test_follow_ups import nurse
from tests.test_listed_names import URL as NAMES
from tests.test_listed_names import listing
from tests.test_restore import P, apply, preview
from tests.test_row_level_security import pytestmark_pg

BOTH = ["listed_names", "dismissed_suggestions"]


def backup(client, h, version=2) -> bytes:
    r = client.get("/api/v1/me/export", headers=h, params={"version": version})
    assert r.status_code == 200, r.text
    return r.content


def names(client, h) -> list[str]:
    return [i["name"] for i in client.get(NAMES, headers=h).json()["items"]]


def category(p: dict, key: str) -> dict:
    return next(c for c in p["categories"] if c["key"] == key)


def forget_all(client, h):
    for i in client.get(NAMES, headers=h).json()["items"]:
        assert client.delete(f"{NAMES}/{i['id']}", headers=h).status_code == 204
    for d in listed(client, h):
        assert client.delete(DISMISSALS, headers=h, params={"key": d["key"]}).status_code == 204


def chosen(client, h):
    listing(client, h, "Priya Raman", "Dr. Okafor")
    assert dismiss(client, h, KEY).status_code == 200


def test_export_delete_both_restore_both_back_and_again_nothing_twice(client):
    h = nurse(client)
    chosen(client, h)
    raw = backup(client, h)
    forget_all(client, h)
    p = preview(client, h, raw).json()
    assert (category(p, "listed_names")["new"], category(p, "dismissed_suggestions")["new"]) == (2, 1)
    assert "replaced with [name] wherever something leaves the app" in category(p, "listed_names")["label"]
    assert "not offered again, on any device" in category(p, "dismissed_suggestions")["label"]
    assert category(p, "listed_names")["samples"] == []  # names aren't shown back in the preview
    assert not any(u["key"] == "listed_names" for u in p["not_restored"])
    r = apply(client, h, raw, BOTH)
    assert r.status_code in (200, 201), r.text
    assert sorted(names(client, h)) == ["Dr. Okafor", "Priya Raman"]
    assert [d["key"] for d in listed(client, h)] == [KEY]
    # The same file again is the same restore; a different restore of it adds nothing twice.
    again = preview(client, h, raw).json()
    assert (
        category(again, "listed_names")["duplicates"],
        category(again, "dismissed_suggestions")["duplicates"],
    ) == (2, 1)
    assert apply(client, h, raw, ["listed_names"]).status_code in (200, 201)
    assert sorted(names(client, h)) == ["Dr. Okafor", "Priya Raman"]


def test_a_name_already_here_in_another_letter_case_is_already_here(client):
    h = nurse(client)
    listing(client, h, "Priya Raman")
    raw = backup(client, h)
    forget_all(client, h)
    listing(client, h, "PRIYA   raman")
    c = category(preview(client, h, raw).json(), "listed_names")
    assert (c["new"], c["duplicates"]) == (0, 1)


def test_names_over_the_lists_limit_are_counted_never_named(client, monkeypatch):
    monkeypatch.setattr(listed_names, "MAX_NAMES", 3)
    from app.services import restore

    monkeypatch.setattr(restore, "MAX_NAMES", 3)
    h = nurse(client)
    listing(client, h, "Ana One", "Ben Two", "Cy Three")
    raw = backup(client, h)
    forget_all(client, h)
    listing(client, h, "Dee Four", "Eve Five")
    p = preview(client, h, raw).json()
    c = category(p, "listed_names")
    assert c["new"] == 1 and c["skipped"] == [{"reason": "Over the list's limit of 3 names", "count": 2}]
    assert not any(n in json.dumps(c) for n in ("Ana", "Ben", "Cy"))
    apply(client, h, raw, ["listed_names"])
    assert len(names(client, h)) == 3


def test_a_dismissal_whose_suggestion_no_longer_exists_is_left_out_with_the_reason(client):
    h = nurse(client)
    raw = json.loads(backup(client, h))
    raw["dismissed_suggestions"] = [
        {"key": "question-follow-up:registered-nurse/no-such>question", "kind": "question_follow_up"},
        {"key": KEY, "kind": "question_follow_up", "dismissed_at": "2026-11-10T09:00:00+00:00"},
    ]
    p = preview(client, h, json.dumps(raw).encode()).json()
    c = category(p, "dismissed_suggestions")
    assert c["new"] == 1
    assert c["skipped"] == [
        {
            "reason": "The suggestion it dismissed isn't offered any more (a retired question or a removed pair)",
            "count": 1,
        }
    ]
    apply(client, h, json.dumps(raw).encode(), ["dismissed_suggestions"])
    [d] = listed(client, h)
    assert d["key"] == KEY and d["dismissed_at"].startswith("2026-11-10")  # its own time kept


def test_undo_keeps_a_suggestion_offered_again_and_a_name_renamed_since(client):
    h = nurse(client)
    chosen(client, h)
    raw = backup(client, h)
    forget_all(client, h)
    batch = apply(client, h, raw, BOTH).json()
    # Since the restore: one suggestion offered again, one name renamed.
    assert client.delete(DISMISSALS, headers=h, params={"key": KEY}).status_code == 204
    renamed = next(i for i in client.get(NAMES, headers=h).json()["items"] if i["name"] == "Dr. Okafor")
    assert (
        client.patch(f"{NAMES}/{renamed['id']}", headers=h, json={"name": "Dr. Ada Okafor"}).status_code
        == 200
    )
    out = client.post(f"{P}/batches/{batch['id']}/remove", headers=h).json()
    assert out["removal"] == {"removed": 1, "kept_edited": 1, "already_gone": 1}
    assert names(client, h) == ["Dr. Ada Okafor"]
    assert listed(client, h) == []  # offered again stays offered


def test_names_never_reach_the_logs_or_the_restores_own_record(client, caplog, capsys):
    canary = "Zelphine Quorrow"
    caplog.set_level(logging.DEBUG)
    h = nurse(client)
    listing(client, h, canary)
    raw = backup(client, h)
    forget_all(client, h)
    caplog.clear()
    preview(client, h, raw)
    batch = apply(client, h, raw, ["listed_names"]).json()
    assert canary in names(client, h)
    logged = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    out = capsys.readouterr()
    assert caplog.records and canary not in logged and canary.split()[0] not in logged
    assert canary not in out.out and canary not in out.err
    with client.app.state.session_factory() as db:
        b = db.get(ImportBatch, batch["id"])
        records = db.scalars(select(ImportedRecord).where(ImportedRecord.batch_id == b.id)).all()
        stored = json.dumps({"counts": b.counts, "records": [(r.kind, r.fingerprint) for r in records]})
    assert canary not in stored and canary.casefold() not in stored and "Zelphine" not in stored
    assert b.counts["listed_names"] == {"added": 1, "duplicates": 0, "skipped": 0}


def test_a_file_from_another_account_restores_into_this_one_only_and_says_where_it_came_from(client):
    a = nurse(client)
    chosen(client, a)
    raw = backup(client, a)
    b = nurse(client, email="bea@example.com")
    p = preview(client, b, raw).json()
    assert p["from_other_account"] is True
    apply(client, b, raw, BOTH)
    assert sorted(names(client, b)) == ["Dr. Okafor", "Priya Raman"]
    assert [d["key"] for d in listed(client, b)] == [KEY]
    with client.app.state.session_factory() as db:  # the other account's rows are untouched
        owners = {r.user_id for r in db.scalars(select(ListedName))}
        assert len(owners) == 2 and db.query(DismissedSuggestion).count() == 2


def test_a_version_1_file_restores_both_too_they_need_no_ids(client):
    h = nurse(client)
    chosen(client, h)
    raw = backup(client, h, version=1)
    forget_all(client, h)
    apply(client, h, raw, BOTH)
    assert len(names(client, h)) == 2 and len(listed(client, h)) == 1


@pytestmark_pg
def test_on_postgresql_a_restore_reads_and_writes_only_this_accounts_rows(client, monkeypatch):
    """Row-level security keeps the planner to this account's names and dismissals even if its
    reads forget the owner (the bug it exists for): another account's same name isn't "already here"."""
    from app.services import restore

    other = nurse(client, email="bea@example.com")
    chosen(client, other)
    h = nurse(client)
    chosen(client, h)
    raw = backup(client, h)
    forget_all(client, h)
    real = restore.Restore._existing

    def careless(self):  # the real one also names the account; this one reads every name it can
        found = real(self)
        found["listed_names"] |= set(self.db.scalars(select(ListedName.folded)))
        found["dismissed_suggestions"] |= set(self.db.scalars(select(DismissedSuggestion.key)))
        return found

    monkeypatch.setattr(restore.Restore, "_existing", careless)
    p = preview(client, h, raw).json()
    assert (category(p, "listed_names")["new"], category(p, "dismissed_suggestions")["new"]) == (2, 1)
