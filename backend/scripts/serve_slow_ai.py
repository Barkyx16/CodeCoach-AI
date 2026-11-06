"""Serve the API with a deliberately slow fake AI provider, for load tests only.

    DATABASE_URL=... python scripts/serve_slow_ai.py --delay 10 --cap 8 --port 8000

Every AI call sleeps `--delay` seconds, then answers like the offline coach, so a load test can
see what a slow or overloaded paid provider does to everyone else, without calling (or paying)
any provider. `--cap` is AI_MAX_CONCURRENT_CALLS (use a large number to see the uncapped
behaviour). Refuses to start with ENVIRONMENT=production.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import replace

import uvicorn

from app.config import get_settings
from app.main import create_app
from app.services.ai.bounded import BoundedProvider
from app.services.ai.offline import OfflineCoach


class SlowFakeProvider:
    name = "anthropic"  # behaves like a paid provider: capped, and falls back when busy
    model = "synthetic-slow"

    def __init__(self, delay: float):
        self.delay = delay
        self.offline = OfflineCoach()

    def _slow(self, method: str, ctx):
        time.sleep(self.delay)
        return replace(getattr(self.offline, method)(ctx), provider="slow-fake")

    def hint(self, ctx):
        return self._slow("hint", ctx)

    def review(self, ctx):
        return self._slow("review", ctx)

    def explain_failure(self, ctx):
        return self._slow("explain_failure", ctx)

    def interview_turn(self, ctx):
        return self._slow("interview_turn", ctx)

    def evaluate_interview(self, ctx):
        return self._slow("evaluate_interview", ctx)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--cap", type=int, default=8)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment == "production" or os.environ.get("ENVIRONMENT") == "production":
        raise SystemExit("serve_slow_ai.py is for load tests only")
    app = create_app(settings)
    app.state.ai_provider = BoundedProvider(SlowFakeProvider(args.delay), args.cap)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
