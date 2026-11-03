"""HTTP client for the isolated runner service (runner/). The API never runs code itself."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


class RunnerUnavailable(Exception):
    """Infrastructure problem talking to the runner (network, 5xx, capacity). Retryable."""


@dataclass(frozen=True)
class RunnerResult:
    status: str  # ok | compile_error | timeout | memory_limit | output_limit | sandbox_error
    exit_code: int | None
    stdout: str
    stderr: str
    compile_output: str | None
    run_started: bool
    output_truncated: bool
    duration_ms: int


class RunnerAuthError(RunnerUnavailable):
    """The runner refused our token: a configuration problem, not a learner problem."""


class Runner(Protocol):
    def run(self, files: dict[str, str], nonce: str, time_limit_s: float) -> RunnerResult: ...


class HttpRunner:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_s: float = 90.0,
        transport: httpx.BaseTransport | None = None,
        ca_bundle: str | None = None,
    ):
        # TLS certificates are always verified; a private CA can be added, never verification removed.
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            transport=transport,
            verify=ca_bundle or True,
            headers={"Authorization": f"Bearer {token}"},
        )

    def status(self, timeout_s: float = 3.0) -> bool:
        """Authenticated readiness probe: True when the runner can start sandboxes now."""
        try:
            r = self._client.get("/v1/status", timeout=timeout_s)
        except httpx.HTTPError as exc:
            raise RunnerUnavailable(f"runner unreachable: {exc.__class__.__name__}") from exc
        if r.status_code in (401, 403):
            raise RunnerAuthError("runner rejected the token")
        if r.status_code != 200:
            raise RunnerUnavailable(f"runner returned HTTP {r.status_code}")
        return bool(r.json().get("ready"))

    def run(self, files: dict[str, str], nonce: str, time_limit_s: float) -> RunnerResult:
        try:
            r = self._client.post(
                "/v1/run", json={"files": files, "nonce": nonce, "time_limit_s": time_limit_s}
            )
        except httpx.HTTPError as exc:
            raise RunnerUnavailable(f"runner unreachable: {exc.__class__.__name__}") from exc
        if r.status_code in (429, 503) or r.status_code >= 500:
            raise RunnerUnavailable(f"runner returned HTTP {r.status_code}")
        if r.status_code != 200:
            # 401/413/422 are configuration or contract bugs, not learner errors; surface them.
            raise RunnerUnavailable(f"runner rejected the job: HTTP {r.status_code}")
        d = r.json()
        return RunnerResult(**{k: d.get(k) for k in RunnerResult.__dataclass_fields__})

    def close(self) -> None:
        self._client.close()
