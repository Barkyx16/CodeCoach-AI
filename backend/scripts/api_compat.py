"""Is a newer OpenAPI document backward compatible with an older one, for the clients of the older?

    git show <old>:docs/openapi.json > /tmp/old.json
    python scripts/api_compat.py /tmp/old.json docs/openapi.json

Reports, per operation the old document has:
- removed operations;
- request body fields that the new document requires and the old didn't (an old client wouldn't
  send them);
- response fields (2xx) the old document had and the new one lacks (an old client may read them);
- enum values a response field could have that the old document didn't list, as notices (an
  old client may not know them).
Exit 1 when anything breaks. Schemas are compared by property name and $ref target, one level
into nested objects and arrays; it is a contract check, not a proof of identical behaviour.
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


def compare(old: dict, new: dict) -> tuple[list[str], list[str]]:
    breaks, notices = [], []
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
            orr, nr = _ok_response(old, op), _ok_response(new, nop)
            if orr is None or nr is None:
                continue
            oprops, nprops = _props(old, orr), _props(new, nr)
            gone = set(oprops) - set(nprops)
            if gone:
                breaks.append(f"{where}: response lost {sorted(gone)}")
            for name in set(oprops) & set(nprops):
                more = _enum(new, nprops[name]) - _enum(old, oprops[name])
                if more and _enum(old, oprops[name]):
                    notices.append(f"{where}: {name} may now be {sorted(more)}")
                inner_old, inner_new = _props(old, oprops[name]), _props(new, nprops[name])
                lost = set(inner_old) - set(inner_new)
                if lost:
                    breaks.append(f"{where}: response {name} lost {sorted(lost)}")
    return breaks, notices


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:])
    breaks, notices = compare(old, new)
    ops = sum(len(v) for v in old["paths"].values())
    for b in breaks:
        print(f"BREAKS  {b}")
    for n in notices:
        print(f"notice  {n}")
    print(f"{ops} operations in the old document: {len(breaks)} breaking, {len(notices)} notices")
    return 1 if breaks else 0


if __name__ == "__main__":
    sys.exit(main())
