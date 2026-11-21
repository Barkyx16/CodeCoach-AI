"""Whiteboard prompts: system-design practice for careers that write code.

Authored here and versioned like Learn units. Only system-design prompts exist for now; process
maps for other careers are left out until reviewed content exists, and the API says so. Each
prompt lists what a good design addresses, as checkable requirement keywords; feedback is built
from those and from the learner's own diagram and reasoning, never from how the diagram looks.
"""

from __future__ import annotations

from dataclasses import dataclass

RUBRIC_VERSION = 1


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    keywords: tuple[str, ...]  # any one, in a label or the learner's notes, counts as addressed


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    title: str
    objective: str
    brief: str
    requirements: tuple[Requirement, ...]
    tracks: tuple[str, ...]


PROMPTS: tuple[Prompt, ...] = (
    Prompt(
        id="sd-url-shortener",
        version=1,
        title="Design a URL shortener",
        objective="Explain how a short link is created and how a click is redirected quickly and reliably.",
        brief=(
            "Users paste a long URL and get a short one. Anyone who opens the short URL is redirected "
            "to the long one. Expect many more redirects than new links."
        ),
        requirements=(
            Requirement(
                "create",
                "Creating a short link (and making codes unique)",
                ("create", "shorten", "generate", "id", "code", "hash"),
            ),
            Requirement(
                "redirect",
                "Redirecting a click to the long URL",
                ("redirect", "lookup", "resolve", "301", "302"),
            ),
            Requirement(
                "store",
                "Where the mapping is stored",
                ("database", "db", "store", "table", "sql", "nosql", "key-value", "kv"),
            ),
            Requirement(
                "read-heavy", "Handling far more reads than writes", ("cache", "replica", "cdn", "read")
            ),
            Requirement(
                "failure",
                "What happens when part of it fails",
                ("retry", "replica", "failover", "fallback", "timeout", "backup"),
            ),
        ),
        tracks=("software-engineer",),
    ),
    Prompt(
        id="sd-rate-limiter",
        version=1,
        title="Design an API rate limiter",
        objective="Explain how requests are counted and limited per client, across several servers.",
        brief=(
            "An API must allow each client a fixed number of requests per minute. It runs on several "
            "servers behind a load balancer, and limits must hold across all of them."
        ),
        requirements=(
            Requirement(
                "identify",
                "Identifying the client (key, user or IP)",
                ("client", "key", "user", "ip", "token"),
            ),
            Requirement(
                "count",
                "Counting requests in a window",
                ("counter", "window", "bucket", "sliding", "fixed", "token bucket", "leaky"),
            ),
            Requirement(
                "shared",
                "Sharing counts across servers",
                ("redis", "shared", "central", "database", "store", "cache"),
            ),
            Requirement(
                "reject", "What a rejected request gets", ("429", "reject", "retry-after", "deny", "block")
            ),
            Requirement(
                "failure",
                "What happens if the counter store is down",
                ("fail open", "fail closed", "fallback", "timeout", "degrade", "local"),
            ),
        ),
        tracks=("software-engineer",),
    ),
    Prompt(
        id="sd-notifications",
        version=1,
        title="Design a notification service",
        objective="Explain how events become notifications that are delivered once, respecting preferences.",
        brief=(
            "Other services publish events (for example, 'order shipped'). Users should get a notification "
            "by email or in the app, according to their preferences, without duplicates."
        ),
        requirements=(
            Requirement(
                "ingest",
                "Receiving events from other services",
                ("event", "publish", "topic", "queue", "kafka", "stream"),
            ),
            Requirement("prefs", "Checking user preferences", ("preference", "settings", "opt", "user")),
            Requirement(
                "deliver",
                "Delivering by channel",
                ("email", "push", "in-app", "channel", "sender", "provider"),
            ),
            Requirement("dedupe", "Avoiding duplicates on retries", ("dedupe", "idempot", "unique", "once")),
            Requirement(
                "failure", "Retries and failures", ("retry", "dead letter", "dlq", "backoff", "failure")
            ),
        ),
        tracks=("software-engineer",),
    ),
)

BY_ID = {p.id: p for p in PROMPTS}


def prompts_for(track: str) -> list[Prompt]:
    return [p for p in PROMPTS if track in p.tracks]
