import type { WhiteboardDiagram } from "@/api/types";

type RawNode = NonNullable<WhiteboardDiagram["nodes"]>[number];
type RawEdge = NonNullable<WhiteboardDiagram["edges"]>[number];
export type DNode = Required<RawNode>;
export type DEdge = Required<RawEdge>;
export type Notes = Required<NonNullable<WhiteboardDiagram["notes"]>>;
export type NodeKind = DNode["kind"];
export type NotesKey = keyof Notes;
/** The editor's diagram: the API format with every default filled in. */
export interface Diagram {
  format: "codecoach-whiteboard";
  version: 1;
  nodes: DNode[];
  edges: DEdge[];
  notes: Notes;
}

export const MAX_NODES = 40;
export const MAX_EDGES = 80;
export const GRID = 20;
export const NODE_W = 140;
export const NODE_H = 56;

export const KIND_LABEL: Record<NodeKind, string> = {
  client: "Client", service: "Service", database: "Database", cache: "Cache", queue: "Queue", external: "External system", other: "Other",
};

export const emptyDiagram = (): Diagram => ({
  format: "codecoach-whiteboard", version: 1, nodes: [], edges: [], notes: { assumptions: "", requirements: "", capacity: "", tradeoffs: "" },
});

/** A diagram from the API (or one the server just checked) with its defaults filled in. */
export function normalize(d: WhiteboardDiagram): Diagram {
  // Only the known fields are copied, so nothing else (say, from a copy kept on this device) rides along.
  const notes: Partial<Notes> = d.notes ?? {};
  return {
    format: "codecoach-whiteboard",
    version: 1,
    nodes: (d.nodes ?? []).map((n) => ({ id: n.id, label: n.label, kind: n.kind ?? "service", x: n.x, y: n.y, group: n.group ?? null })),
    edges: (d.edges ?? []).map((x) => ({ id: x.id, source: x.source, target: x.target, label: x.label ?? "" })),
    notes: { assumptions: notes.assumptions ?? "", requirements: notes.requirements ?? "", capacity: notes.capacity ?? "", tradeoffs: notes.tradeoffs ?? "" },
  };
}

const snap = (v: number) => Math.max(0, Math.min(4000, Math.round(v / GRID) * GRID));

function nextId(prefix: "n" | "e", taken: string[]): string {
  let i = 1;
  while (taken.includes(`${prefix}${i}`)) i += 1;
  return `${prefix}${i}`;
}

export type Action =
  | { type: "load"; diagram: Diagram }
  | { type: "addNode"; label: string; kind: NodeKind }
  | { type: "updateNode"; id: string; patch: Partial<Omit<DNode, "id">> }
  | { type: "moveNode"; id: string; dx: number; dy: number }
  | { type: "placeNode"; id: string; x: number; y: number }
  | { type: "deleteNode"; id: string }
  | { type: "addEdge"; source: string; target: string; label: string }
  | { type: "updateEdge"; id: string; label: string }
  | { type: "deleteEdge"; id: string }
  | { type: "notes"; key: NotesKey; value: string };

/** Pure: one change to a diagram. Bounds are kept here so the editor can't build an invalid one. */
export function apply(d: Diagram, a: Action): Diagram {
  switch (a.type) {
    case "load":
      return a.diagram;
    case "addNode": {
      if (d.nodes.length >= MAX_NODES) return d;
      const id = nextId("n", d.nodes.map((n) => n.id));
      const i = d.nodes.length;
      // Place new components on a loose grid so they never land on top of each other.
      const x = 40 + (i % 4) * (NODE_W + 60);
      const y = 40 + Math.floor(i / 4) * (NODE_H + 60);
      return { ...d, nodes: [...d.nodes, { id, label: a.label.slice(0, 60), kind: a.kind, x, y, group: null }] };
    }
    case "updateNode":
      return { ...d, nodes: d.nodes.map((n) => (n.id === a.id ? { ...n, ...a.patch, label: (a.patch.label ?? n.label).slice(0, 60) } : n)) };
    case "moveNode":
      return { ...d, nodes: d.nodes.map((n) => (n.id === a.id ? { ...n, x: snap(n.x + a.dx), y: snap(n.y + a.dy) } : n)) };
    case "placeNode":
      return { ...d, nodes: d.nodes.map((n) => (n.id === a.id ? { ...n, x: snap(a.x), y: snap(a.y) } : n)) };
    case "deleteNode":
      // Its connections go with it (in the same step, so one Undo brings both back).
      return { ...d, nodes: d.nodes.filter((n) => n.id !== a.id), edges: d.edges.filter((e) => e.source !== a.id && e.target !== a.id) };
    case "addEdge": {
      if (d.edges.length >= MAX_EDGES || a.source === a.target) return d;
      if (!d.nodes.some((n) => n.id === a.source) || !d.nodes.some((n) => n.id === a.target)) return d;
      const id = nextId("e", d.edges.map((e) => e.id));
      return { ...d, edges: [...d.edges, { id, source: a.source, target: a.target, label: a.label.slice(0, 60) }] };
    }
    case "updateEdge":
      return { ...d, edges: d.edges.map((e) => (e.id === a.id ? { ...e, label: a.label.slice(0, 60) } : e)) };
    case "deleteEdge":
      return { ...d, edges: d.edges.filter((e) => e.id !== a.id) };
    case "notes":
      return { ...d, notes: { ...d.notes, [a.key]: a.value.slice(0, 2000) } };
  }
}

export interface History {
  past: Diagram[];
  present: Diagram;
  future: Diagram[];
}

export type HistoryAction = Action | { type: "undo" } | { type: "redo" } | { type: "reset"; diagram: Diagram };

/** Undo and redo over whole diagrams (small, so snapshots are cheap). Loading resets history. */
export function history(h: History, a: HistoryAction): History {
  if (a.type === "undo") return h.past.length ? { past: h.past.slice(0, -1), present: h.past.at(-1)!, future: [h.present, ...h.future] } : h;
  if (a.type === "redo") return h.future.length ? { past: [...h.past, h.present], present: h.future[0]!, future: h.future.slice(1) } : h;
  if (a.type === "reset") return { past: [], present: a.diagram, future: [] };
  const next = apply(h.present, a);
  if (next === h.present) return h;
  return { past: [...h.past, h.present].slice(-100), present: next, future: [] };
}

/** The diagram in words, for screen readers and as a plain summary. */
export function describe(d: Diagram): string[] {
  const name = (id: string) => d.nodes.find((n) => n.id === id)?.label || id;
  return [
    ...d.nodes.map((n) => `${n.label || "(no name)"}: ${KIND_LABEL[n.kind].toLowerCase()} (${n.id})`),
    ...d.edges.map((e) => `${name(e.source)} → ${name(e.target)}${e.label ? `: ${e.label}` : ""} (${e.id})`),
  ];
}

/** The view box that fits every component, with a margin. */
export function fit(d: Diagram): { x: number; y: number; w: number; h: number } {
  if (!d.nodes.length) return { x: 0, y: 0, w: 800, h: 480 };
  const xs = d.nodes.map((n) => n.x), ys = d.nodes.map((n) => n.y);
  const x = Math.min(...xs) - 40, y = Math.min(...ys) - 56; // room for a group's name above it
  return { x, y, w: Math.max(...xs) + NODE_W + 40 - x, h: Math.max(...ys) + NODE_H + 40 - y };
}

/**
 * A canonical form of the diagram's content, so "changed?" doesn't depend on key order or on the
 * whitespace the server trims.
 */
export function fingerprint(d: Diagram): string {
  return JSON.stringify([
    d.nodes.map((n) => [n.id, n.label.trim(), n.kind, n.x, n.y, n.group?.trim() || null]),
    d.edges.map((e) => [e.id, e.source, e.target, e.label.trim()]),
    [d.notes.assumptions.trim(), d.notes.requirements.trim(), d.notes.capacity.trim(), d.notes.tradeoffs.trim()],
  ]);
}

/** The box around each named group of components, drawn behind them. */
export function groupBoxes(d: Diagram): { name: string; x: number; y: number; w: number; h: number }[] {
  const by = new Map<string, DNode[]>();
  for (const n of d.nodes) {
    const g = n.group?.trim();
    if (g) by.set(g, [...(by.get(g) ?? []), n]);
  }
  return [...by.entries()].map(([name, ns]) => {
    const x = Math.min(...ns.map((n) => n.x)) - 16, y = Math.min(...ns.map((n) => n.y)) - 30;
    return { name, x, y, w: Math.max(...ns.map((n) => n.x)) + NODE_W + 16 - x, h: Math.max(...ns.map((n) => n.y)) + NODE_H + 16 - y };
  });
}
