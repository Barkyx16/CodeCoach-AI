"""Is a newer OpenAPI document backward compatible with an older one, for the clients of the older?

    git show <old>:docs/openapi.json > /tmp/old.json
    python scripts/api_compat.py /tmp/old.json docs/openapi.json [--strict]

Reports, per operation the old document has:
- removed operations;
- request body fields that the new document requires and the old didn't (an old client wouldn't
  send them);
- response fields (2xx) the old document had and the new one lacks (an old client may read them);
- enum values a response field could have that the old document didn't list, as consumer-
  sensitive (an old client may reject or misread them: test the consumer);
- request enums that stopped accepting a value, as breaking.
Exit 1 when anything breaks, and with --strict also when anything is consumer-sensitive.
Schemas are compared by property name and $ref target, one level into nested objects and
arrays; it is a contract check, not a proof of identical behaviour.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _resolve(doc: dict, schema: dict) -> dict:
    seen = 0
    while "$ref" in schema and seen < 20:
        schema = doc["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
        seen += 1
    return schema


def _variants(doc: dict, schema: dict) -> list[dict]:
    schema = _resolve(doc, schema)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            return [v for s in schema[key] for v in _variants(doc, s)]
    return [schema]


def _props(doc: dict, schema: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for v in _variants(doc, schema):
        if v.get("type") == "array" and "items" in v:
            out.update(_props(doc, v["items"]))
        out.update(v.get("properties", {}))
    return out


def _required(doc: dict, schema: dict) -> set[str]:
    return {r for v in _variants(doc, schema) for r in v.get("required", [])}


def _enum(doc: dict, schema: dict) -> set[str]:
    return {e for v in _variants(doc, schema) for e in v.get("enum", []) if e is not None}


def _body(doc: dict, op: dict) -> dict | None:
    return (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema")


def _ok_response(doc: dict, op: dict) -> dict | None:
    for code, r in op.get("responses", {}).items():
        if code.startswith("2"):
            return r.get("content", {}).get("application/json", {}).get("schema")
    return None


def compare(old: dict, new: dict) -> tuple[list[str], list[str], list[str]]:
    """(breaking, consumer_sensitive, compatible), for clients written against `old`.

    Directions (Verification brief 06):
    - breaking: an operation removed; a request field newly required; a request enum that no
      longer accepts a value it used to; a response field (one level in) removed.
    - consumer-sensitive: a response enum with a new value. A strict client may reject it; a
      permissive one may misread it (an old page reading evidence_level "unknown" as scoreable).
      Only a test of the consumer can say which; the rollout has to account for it.
    - compatible: optional request or response fields added, a request enum accepting more.
    Out of scope (not compared): type changes, formats, defaults, status codes, headers.
    """
    breaks: list[str] = []
    sensitive: list[str] = []
    compatible: list[str] = []
    for path, ops in old["paths"].items():
        for method, op in ops.items():
            where = f"{method.upper()} {path}"
            nop = new["paths"].get(path, {}).get(method)
            if nop is None:
                breaks.append(f"{where}: removed")
                continue
            ob, nb = _body(old, op), _body(new, nop)
            if nb is not None:
                extra = _required(new, nb) - (_required(old, ob) if ob else set())
                if extra:
                    breaks.append(f"{where}: request now requires {sorted(extra)}")
                if ob is not None:
                    oreq, nreq = _props(old, ob), _props(new, nb)
                    for name in set(oreq) & set(nreq):
                        before, after = _enum(old, oreq[name]), _enum(new, nreq[name])
                        if before and after and before - after:
                            breaks.append(
                                f"{where}: request {name} no longer accepts {sorted(before - after)}"
                            )
                        elif before and after - before:
                            compatible.append(
                                f"{where}: request {name} also accepts {sorted(after - before)}"
                            )
                    added = set(nreq) - set(oreq) - _required(new, nb)
                    if added:
                        compatible.append(f"{where}: optional request fields added {sorted(added)}")
            orr, nr = _ok_response(old, op), _ok_response(new, nop)
            if orr is None or nr is None:
                continue
            oprops, nprops = _props(old, orr), _props(new, nr)
            gone = set(oprops) - set(nprops)
            if gone:
                breaks.append(f"{where}: response lost {sorted(gone)}")
            if set(nprops) - set(oprops):
                compatible.append(f"{where}: response fields added {sorted(set(nprops) - set(oprops))}")
            for name in set(oprops) & set(nprops):
                more = _enum(new, nprops[name]) - _enum(old, oprops[name])
                if more and _enum(old, oprops[name]):
                    sensitive.append(
                        f"{where}: response {name} may now be {sorted(more)}; a client that only knows "
                        f"{sorted(_enum(old, oprops[name]))} may reject or misread it"
                    )
                inner_old, inner_new = _props(old, oprops[name]), _props(new, nprops[name])
                lost = set(inner_old) - set(inner_new)
                if lost:
                    breaks.append(f"{where}: response {name} lost {sorted(lost)}")
    return breaks, sensitive, compatible


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--strict"]
    if len(args) != 2:
        raise SystemExit(__doc__)
    strict = "--strict" in sys.argv
    old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args)
    breaks, sensitive, compatible = compare(old, new)
    ops = sum(len(v) for v in old["paths"].values())
    for b in breaks:
        print(f"BREAKING          {b}")
    for c in sensitive:
        print(f"CONSUMER-SENSITIVE {c}")
    print(
        f"{ops} operations in the old document compared: {len(breaks)} breaking, {len(sensitive)} "
        f"consumer-sensitive, {len(compatible)} compatible additions (not listed)"
    )
    return 1 if breaks or (strict and sensitive) else 0


if __name__ == "__main__":
    sys.exit(main())
