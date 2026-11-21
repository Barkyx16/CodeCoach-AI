"""Guest-account retention: inactive demo accounts are deleted, active and registered ones kept."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.cli import main as cli_main
from app.models import AIInteraction, ProgressEvent, RefreshToken, Submission, User
from app.services.retention import prune_inactive_guests
from tests.conftest import auth_headers, register

NOW = datetime.now(UTC)


def guest(client) -> dict:
    return client.post("/api/v1/auth/guest").json()


def age(client, user_id: str, days: int, *, refresh_days: int | None = None, events_days: int | None = None):
    """Pretend the account was created (and last active) `days` ago."""
    with client.app.state.session_factory() as db:
        then = NOW - timedelta(days=days)
        db.get(User, user_id).created_at = then
        for r in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id)):
            r.created_at = NOW - timedelta(days=refresh_days if refresh_days is not None else days)
        for e in db.scalars(select(ProgressEvent).where(ProgressEvent.user_id == user_id)):
            e.created_at = NOW - timedelta(days=events_days if events_days is not None else days)
        db.commit()


def users(client) -> set[str]:
    with client.app.state.session_factory() as db:
        return set(db.scalars(select(User.id)).all())


def test_inactive_guests_are_deleted_with_their_data(client):
    g = guest(client)
    h = auth_headers(g)
    client.post("/api/v1/ai/hint", headers=h, json={"problem_slug": "two-sum", "level": 1})
    client.post(
        "/api/v1/submissions", headers=h, json={"problem_slug": "two-sum", "source_code": "class S {}"}
    )
    age(client, g["user"]["id"], 40)
    with client.app.state.session_factory() as db:
        assert prune_inactive_guests(db, 30) == 1
        for model in (Submission, AIInteraction, ProgressEvent, RefreshToken):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__


def test_recent_activity_keeps_an_old_guest(client):
    by_refresh, by_event, untouched = guest(client), guest(client), guest(client)
    client.get("/api/v1/problems/two-sum", headers=auth_headers(by_event))  # records a visit
    age(client, by_refresh["user"]["id"], 90, refresh_days=2)  # an open tab refreshed recently
    age(client, by_event["user"]["id"], 90, refresh_days=90, events_days=1)
    age(client, untouched["user"]["id"], 90)
    with client.app.state.session_factory() as db:
        assert prune_inactive_guests(db, 30) == 1
    assert untouched["user"]["id"] not in users(client)
    assert {by_refresh["user"]["id"], by_event["user"]["id"]} <= users(client)


def test_registered_accounts_and_new_guests_are_never_pruned(client):
    member = register(client)
    fresh = guest(client)
    age(client, member["user"]["id"], 400)
    with client.app.state.session_factory() as db:
        assert prune_inactive_guests(db, 30) == 0
    assert {member["user"]["id"], fresh["user"]["id"]} <= users(client)


def test_zero_days_disables_retention(client):
    g = guest(client)
    age(client, g["user"]["id"], 400)
    with client.app.state.session_factory() as db:
        assert prune_inactive_guests(db, 0) == 0


def test_cli_command(client, monkeypatch, capsys):
    g = guest(client)
    age(client, g["user"]["id"], 10)
    monkeypatch.setenv("DATABASE_URL", client.app.state.settings.database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert cli_main(["app.cli", "prune-guests", "--days", "7"]) == 0
    finally:
        get_settings.cache_clear()
    assert "Deleted 1 guest accounts inactive for 7+ days" in capsys.readouterr().out
    assert g["user"]["id"] not in users(client)
