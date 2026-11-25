import { useRef, useState, type PointerEvent } from "react";

import { groupBoxes, NODE_H, NODE_W, type Diagram } from "./diagram";

/**
 * The visual canvas. Pointer users drag components to move them; every action here is also in the
 * outline beside it, so nothing needs a pointer. The canvas itself is a single labelled image
 * whose words are in the outline and the summary.
 */
export function Canvas({ diagram, view, selected, highlighted, onSelect, onDrop }: {
  diagram: Diagram;
  view: { x: number; y: number; w: number; h: number };
  selected: string | null;
  highlighted: ReadonlySet<string>;
  onSelect: (id: string | null) => void;
  onDrop: (id: string, x: number, y: number) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; x: number; y: number } | null>(null);
  const byId = new Map(diagram.nodes.map((n) => [n.id, n]));

  const toSvg = (e: PointerEvent) => {
    const pt = svg.current!.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const m = svg.current!.getScreenCTM();
    return m ? pt.matrixTransform(m.inverse()) : { x: e.clientX, y: e.clientY };
  };

  return (
    <svg ref={svg} className="wb-canvas" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="img"
      aria-label={`Diagram with ${diagram.nodes.length} components and ${diagram.edges.length} connections. The outline lists them and lets you change everything from the keyboard.`}
      onPointerMove={(e) => {
        if (!drag) return;
        const p = toSvg(e);
        setDrag({ ...drag, x: p.x - drag.dx, y: p.y - drag.dy });
      }}
      onPointerUp={() => {
        if (drag) onDrop(drag.id, drag.x, drag.y);
        setDrag(null);
      }}
      onPointerLeave={() => setDrag(null)}
      onPointerCancel={() => setDrag(null)}
      onClick={(e) => { if (e.target === svg.current) onSelect(null); }}>
      <defs>
        <marker id="wb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" className="wb-arrow" />
        </marker>
      </defs>
      {groupBoxes(diagram).map((g) => (
        <g key={g.name} className="wb-group">
          <rect x={g.x} y={g.y} width={g.w} height={g.h} rx={14} />
          <text x={g.x + 10} y={g.y + 18}>{g.name}</text>
        </g>
      ))}
      {diagram.edges.map((e) => {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) return null;
        const pa = drag?.id === a.id ? drag : a, pb = drag?.id === b.id ? drag : b;
        const x1 = pa.x + NODE_W / 2, y1 = pa.y + NODE_H / 2, x2 = pb.x + NODE_W / 2, y2 = pb.y + NODE_H / 2;
        return (
          <g key={e.id} className={`wb-edge${highlighted.has(e.id) ? " wb-edge--highlight" : ""}`} data-id={e.id}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd="url(#wb-arrow)" />
            {e.label && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} textAnchor="middle">{e.label}</text>}
          </g>
        );
      })}
      {diagram.nodes.map((n) => {
        const p = drag?.id === n.id ? drag : n;
        return (
          <g key={n.id} data-id={n.id} transform={`translate(${p.x} ${p.y})`}
            className={`wb-node wb-node--${n.kind}${selected === n.id ? " wb-node--selected" : ""}${highlighted.has(n.id) ? " wb-node--highlight" : ""}`}
            onPointerDown={(e) => {
              if (e.button !== 0) return;
              e.currentTarget.ownerSVGElement?.setPointerCapture?.(e.pointerId);
              const q = toSvg(e);
              onSelect(n.id);
              setDrag({ id: n.id, dx: q.x - n.x, dy: q.y - n.y, x: n.x, y: n.y });
            }}>
            <rect width={NODE_W} height={NODE_H} rx={10} />
            <text x={NODE_W / 2} y={NODE_H / 2 - 4} textAnchor="middle" className="wb-node__label">{n.label.length > 18 ? `${n.label.slice(0, 17)}…` : n.label || "(no name)"}</text>
            <text x={NODE_W / 2} y={NODE_H / 2 + 14} textAnchor="middle" className="wb-node__kind">{n.kind} · {n.id}</text>
          </g>
        );
      })}
    </svg>
  );
}
