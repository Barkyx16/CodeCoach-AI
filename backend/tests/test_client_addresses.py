"""Rate limits are per client address, so the API must see the visitor's address, not the proxy's.

In the production compose file a proxy on the host reaches the API through Docker's gateway
(172.x.0.1), never 127.0.0.1, which is all uvicorn believes by default. Then every visitor shared
one address and one sign-in rate limit (10 a minute, for the whole site). The compose file now sets
FORWARDED_ALLOW_IPS; these tests feed its exact value to uvicorn's own middleware. The compose
rehearsal (scripts/rehearse_production_storage.sh, step 2c) checks the same through Docker."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.services.preflight import READY, UNVERIFIED, _client_address_check

COMPOSE = Path(__file__).resolve().parents[2] / "deploy" / "docker-compose.production.yml"


def compose_default() -> str:
    m = re.search(r"FORWARDED_ALLOW_IPS: \$\{FORWARDED_ALLOW_IPS:-([^}]+)\}", COMPOSE.read_text())
    assert m, "the api service sets FORWARDED_ALLOW_IPS"
    return m.group(1)


def seen_client(trusted: str, peer: str, forwarded: str | None) -> str:
    """The client address the app sees, through uvicorn's middleware, as `--proxy-headers` runs it."""
    seen: dict[str, str] = {}

    async def app(scope, receive, send):
        seen["client"] = scope["client"][0]

    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    scope = {"type": "http", "client": (peer, 50000), "headers": headers, "scheme": "http"}
    asyncio.run(ProxyHeadersMiddleware(app, trusted_hosts=trusted)(scope, None, None))
    return seen["client"]


@pytest.mark.parametrize("gateway", ["172.17.0.1", "172.18.0.1", "192.168.16.1", "10.0.5.1"])
def test_the_proxy_reaching_the_api_through_dockers_gateway_is_believed(gateway):
    assert seen_client(compose_default(), gateway, "203.0.113.7") == "203.0.113.7"


def test_two_visitors_behind_the_proxy_get_two_addresses():
    trusted = compose_default()
    assert seen_client(trusted, "172.18.0.1", "203.0.113.7") != seen_client(
        trusted, "172.18.0.1", "198.51.100.4"
    )


def test_a_client_that_isnt_the_proxy_cant_choose_its_address():
    # A public address connecting directly (if the port were ever exposed): its header is ignored.
    assert seen_client(compose_default(), "203.0.113.50", "198.51.100.1") == "203.0.113.50"


def test_uvicorns_own_default_is_what_broke_it():
    """Without the setting, the proxy's address is everyone's address."""
    assert seen_client("127.0.0.1", "172.18.0.1", "203.0.113.7") == "172.18.0.1"


def test_the_preflight_says_whether_forwarded_addresses_are_believed():
    assert _client_address_check(None).status == UNVERIFIED
    assert "every visitor shares" in _client_address_check(None).reason
    assert _client_address_check("10.0.0.0/8, *").status == UNVERIFIED
    ok = _client_address_check("172.18.0.1")
    assert ok.status == READY and "172.18.0.1" not in ok.reason  # set, value not shown
