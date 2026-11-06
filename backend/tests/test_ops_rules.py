"""The checked-in Prometheus rules (ops/prometheus) must match what the app actually exports.

`promtool` validates PromQL syntax and alert timing (ops/prometheus/codecoach-rules.test.yml);
this test keeps the rules honest from the app's side: every metric and label they use exists,
every alert waits before firing, ratio alerts need real traffic, and every runbook link resolves.
"""

import re
from pathlib import Path

import pytest
import yaml

from app.metrics import Metrics

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "ops" / "prometheus" / "codecoach-rules.yml"
DOC = ROOT / "docs" / "OBSERVABILITY.md"

pytestmark = pytest.mark.skipif(
    not RULES.exists(), reason="ops/ not present (e.g. inside the Docker build context)"
)


def exported() -> dict[str, set[str]]:
    """Metric name -> its label names, from the app's own registry."""
    out: dict[str, set[str]] = {}
    for family in Metrics().registry.collect():
        names = {
            family.name,
            f"{family.name}_total",
            f"{family.name}_bucket",
            f"{family.name}_count",
            f"{family.name}_sum",
        }
        labels = {k for s in family.samples for k in s.labels} | set(getattr(family, "_labelnames", ()))
        for n in names:
            out[n] = labels | {"le"}
    # Label names of metrics that have no samples yet come from the collectors themselves.
    m = Metrics()
    for attr in vars(m).values():
        name = getattr(attr, "_name", None)
        if name:
            for n in (name, f"{name}_total", f"{name}_bucket", f"{name}_count", f"{name}_sum"):
                out.setdefault(n, set()).update(getattr(attr, "_labelnames", ()), {"le"})
    return out


def rules():
    data = yaml.safe_load(RULES.read_text())
    return [rule for group in data["groups"] for rule in group["rules"]]


def test_every_metric_and_label_in_the_rules_is_exported():
    metrics = exported()
    recorded = {r["record"] for r in rules() if "record" in r}
    for rule in rules():
        expr = rule["expr"]
        for name in set(re.findall(r"\b(codecoach:[a-z0-9_:]+)", expr)):
            assert name in recorded, f"{name} is used but never recorded"
        for name, matchers in re.findall(r"\b(codecoach_[a-z_]+)(?:\{([^}]*)\})?", expr):
            assert name in metrics, f"{name} is not exported by app/metrics.py"
            for label in re.findall(r"([a-z_]+)\s*(?:=~|!~|!=|=)", matchers or ""):
                assert label in metrics[name], f"{name} has no label {label!r}"
        for label in re.findall(r"by \(([^)]*)\)", expr):
            for name in (n.strip() for n in label.split(",")):
                assert any(name in labels for labels in metrics.values()), name


def test_alerts_wait_before_firing_need_traffic_and_link_a_runbook():
    doc = DOC.read_text()
    anchors = {
        "#" + re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")
        for h in re.findall(r"^#+ (.+)$", doc, re.M)
    }
    alerts = [r for r in rules() if "alert" in r]
    assert len(alerts) >= 5
    for alert in alerts:
        minutes = int(re.fullmatch(r"(\d+)m", alert["for"]).group(1))
        assert 5 <= minutes <= 60, alert["alert"]
        assert alert["labels"]["severity"] in {"page", "ticket"}
        runbook = alert["annotations"]["runbook"]
        assert (
            runbook.startswith("docs/OBSERVABILITY.md#") and runbook.split("OBSERVABILITY.md")[1] in anchors
        ), runbook
        if "ratio" in alert["expr"]:  # one failure on a quiet night must not page anyone
            assert re.search(r"increase\(.*\)\)\s*>=\s*\d+", alert["expr"]), alert["alert"]


def test_the_rule_tests_cover_the_paging_alerts_they_name():
    tests = yaml.safe_load((RULES.parent / "codecoach-rules.test.yml").read_text())
    names = {a["alertname"] for t in tests["tests"] for a in t["alert_rule_test"]}
    assert names <= {r["alert"] for r in rules() if "alert" in r}
    assert {"CodeCoachRoundActionsFailing", "CodeCoachJudgeQueueStuck"} <= names
