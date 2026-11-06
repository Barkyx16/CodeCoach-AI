import { apply, describe as describeDiagram, emptyDiagram, fingerprint, groupBoxes, history, type History } from "./diagram";

const start = (): History => ({ past: [], present: emptyDiagram(), future: [] });

describe("diagram editing", () => {
  it("adds, connects, renames and moves on a grid, within bounds", () => {
    let d = apply(emptyDiagram(), { type: "addNode", label: "Browser", kind: "client" });
    d = apply(d, { type: "addNode", label: "API", kind: "service" });
    expect(d.nodes.map((n) => n.id)).toEqual(["n1", "n2"]);
    expect(d.nodes[0]!.x).not.toBe(d.nodes[1]!.x); // never on top of each other
    d = apply(d, { type: "addEdge", source: "n1", target: "n2", label: "requests" });
    expect(apply(d, { type: "addEdge", source: "n1", target: "n1", label: "" })).toBe(d); // no self-connection
    expect(apply(d, { type: "addEdge", source: "n1", target: "n9", label: "" })).toBe(d); // no broken connection
    d = apply(d, { type: "moveNode", id: "n1", dx: 47, dy: -1000 });
    expect([d.nodes[0]!.x % 20, d.nodes[0]!.y]).toEqual([0, 0]);
    d = apply(d, { type: "updateNode", id: "n2", patch: { label: "x".repeat(80) } });
    expect(d.nodes[1]!.label).toHaveLength(60);
    expect(describeDiagram(d)).toContain("Browser → " + "x".repeat(60) + ": requests (e1)");
  });

  it("deletes a component with its connections, and one undo brings both back", () => {
    let h = start();
    for (const a of [{ type: "addNode", label: "A", kind: "service" }, { type: "addNode", label: "B", kind: "database" }, { type: "addEdge", source: "n1", target: "n2", label: "" }] as const) h = history(h, a);
    h = history(h, { type: "deleteNode", id: "n2" });
    expect(h.present.edges).toEqual([]);
    h = history(h, { type: "undo" });
    expect(h.present.nodes).toHaveLength(2);
    expect(h.present.edges).toHaveLength(1);
    h = history(h, { type: "redo" });
    expect(h.present.nodes).toHaveLength(1);
    h = history(h, { type: "undo" });
    h = history(h, { type: "addNode", label: "C", kind: "cache" });
    expect(h.future).toEqual([]); // a new change clears redo
  });
});

describe("diagram identity and groups", () => {
  it("treats key order and trimmed whitespace as the same diagram, and a real edit as different", () => {
    const d = apply(emptyDiagram(), { type: "addNode", label: "API", kind: "service" });
    const reordered = { ...d, nodes: d.nodes.map((n) => ({ group: n.group, y: n.y, x: n.x, kind: n.kind, label: `${n.label} `, id: n.id })) };
    expect(fingerprint(reordered)).toBe(fingerprint(d));
    expect(fingerprint(apply(d, { type: "moveNode", id: "n1", dx: 40, dy: 0 }))).not.toBe(fingerprint(d));
  });

  it("draws one box per named group around its components", () => {
    let d = apply(emptyDiagram(), { type: "addNode", label: "A", kind: "service" });
    d = apply(d, { type: "addNode", label: "B", kind: "cache" });
    d = apply(d, { type: "addNode", label: "C", kind: "database" });
    d = apply(d, { type: "updateNode", id: "n1", patch: { group: "Read path" } });
    d = apply(d, { type: "updateNode", id: "n2", patch: { group: "Read path " } });
    const boxes = groupBoxes(d);
    expect(boxes.map((b) => b.name)).toEqual(["Read path"]);
    expect(boxes[0]!.x).toBeLessThan(d.nodes[0]!.x);
    expect(boxes[0]!.x + boxes[0]!.w).toBeGreaterThan(d.nodes[1]!.x);
  });
});
