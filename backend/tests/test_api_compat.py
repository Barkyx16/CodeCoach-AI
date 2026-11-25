"""The API contract comparison (Verification brief 06): each compatibility direction on a small
fixture, expected result written first, including the ones it must not flag."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "api_compat", Path(__file__).resolve().parents[1] / "scripts" / "api_compat.py"
)
assert _spec and _spec.loader
api_compat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_compat)


def doc() -> dict:
    return {
        "paths": {
            "/a": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/In"}}}
                    },
                    "responses": {
                        "201": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Out"}}}
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "In": {
                    "properties": {"text": {"type": "string"}, "mode": {"enum": ["fast", "slow"]}},
                    "required": ["text"],
                },
                "Out": {
                    "properties": {"id": {"type": "string"}, "level": {"enum": ["low", "high"]}},
                    "required": ["id"],
                },
            }
        },
    }


def changed(fn) -> dict:
    d = copy.deepcopy(doc())
    fn(d)
    return d


S = lambda d: d["components"]["schemas"]  # noqa: E731


@pytest.mark.parametrize(
    ("name", "change", "expect"),
    [
        ("no change", lambda d: None, (0, 0)),
        ("operation removed", lambda d: d["paths"].pop("/a"), (1, 0)),
        ("request field newly required", lambda d: S(d)["In"]["required"].append("mode"), (1, 0)),
        ("request enum restricted", lambda d: S(d)["In"]["properties"]["mode"].update(enum=["fast"]), (1, 0)),
        ("response field removed", lambda d: S(d)["Out"]["properties"].pop("level"), (1, 0)),
        # consumer-sensitive: compatible in structure, unsafe for a closed client
        (
            "response enum extended",
            lambda d: S(d)["Out"]["properties"]["level"].update(enum=["low", "high", "unknown"]),
            (0, 1),
        ),
        # compatible: these must not be flagged
        (
            "request enum extended",
            lambda d: S(d)["In"]["properties"]["mode"].update(enum=["fast", "slow", "auto"]),
            (0, 0),
        ),
        (
            "optional request field added",
            lambda d: S(d)["In"]["properties"].update(note={"type": "string"}),
            (0, 0),
        ),
        (
            "response field added",
            lambda d: S(d)["Out"]["properties"].update(extra={"type": "string"}),
            (0, 0),
        ),
        ("new operation added", lambda d: d["paths"].update({"/b": {"get": {"responses": {}}}}), (0, 0)),
    ],
)
def test_each_direction_is_classified(name, change, expect):
    breaks, sensitive, _ = api_compat.compare(doc(), changed(change))
    assert (len(breaks), len(sensitive)) == expect, (name, breaks, sensitive)


def test_reversing_a_compatible_change_is_reported_as_breaking():
    """A field added is compatible; the same change seen backwards (removed) breaks the old client."""
    added = changed(lambda d: S(d)["Out"]["properties"].update(extra={"type": "string"}))
    assert api_compat.compare(doc(), added)[0] == []
    assert api_compat.compare(added, doc())[0] == ["POST /a: response lost ['extra']"]
