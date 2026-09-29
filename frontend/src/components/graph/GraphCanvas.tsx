"use client";

import { PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { forceLayout, Point } from "@/lib/forceLayout";
import {
  LABEL_COLOR,
  LABEL_RADIUS,
  nodeCaption,
  nodeColor,
  primaryLabel,
  truncate,
} from "@/lib/graphStyle";
import { GraphData, GraphNode } from "@/lib/types";

const WIDTH = 1000;
const HEIGHT = 620;

// Captions for every node stop being readable past this; above it only
// the selected node, its neighbours and the hovered one are captioned.
const CAPTION_ALL_BELOW = 70;

// Few enough per result to caption always: they are the hubs everything
// else hangs off, and an uncaptioned hub is a blue dot.
const ALWAYS_CAPTIONED = new Set(["Article", "Source", "Verdict"]);

interface Transform {
  x: number;
  y: number;
  k: number;
}

/** The transform that shows every node, with room for captions. */
function fitTransform(positions: Map<string, Point>): Transform {
  if (positions.size === 0) return { x: 0, y: 0, k: 1 };

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  positions.forEach(({ x, y }) => {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  });

  const pad = 40;
  const w = Math.max(maxX - minX, 1) + pad * 2;
  const h = Math.max(maxY - minY, 1) + pad * 2;
  const k = Math.min(WIDTH / w, HEIGHT / h, 1.6);

  return {
    k,
    x: (WIDTH - (maxX - minX) * k) / 2 - minX * k,
    y: (HEIGHT - (maxY - minY) * k) / 2 - minY * k,
  };
}

type Drag =
  | { kind: "pan"; startX: number; startY: number; from: Transform; moved: boolean }
  | { kind: "node"; id: string; moved: boolean };

/**
 * Draws a query result as a node-link diagram. Pan by dragging the
 * background, zoom with the wheel, drag a node to move it, click one to
 * select it - the page shows its properties and can expand it.
 */
export function GraphCanvas({
  data,
  selectedId,
  onSelect,
}: {
  data: GraphData;
  selectedId: string | null;
  onSelect: (node: GraphNode | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  const [positions, setPositions] = useState<Map<string, Point>>(new Map());
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, k: 1 });
  const [drag, setDrag] = useState<Drag | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const layoutKey = useMemo(
    () => data.nodes.map((n) => n.id).join("|") + "#" + data.relationships.length,
    [data]
  );

  // Re-lay out when the set of nodes changes. Nodes already placed keep
  // their position (an expanded neighbourhood grows around what you were
  // looking at instead of reshuffling it).
  const positionsRef = useRef(positions);
  positionsRef.current = positions;

  useEffect(() => {
    const next = forceLayout(
      data.nodes.map((n) => n.id),
      data.relationships.map((r) => [r.start, r.end] as [string, string]),
      WIDTH,
      HEIGHT,
      positionsRef.current
    );
    setPositions(next);
    setTransform(fitTransform(next));
  }, [layoutKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const nodeById = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data]);

  // Wheel zoom needs a native, non-passive listener: React attaches wheel
  // handlers as passive, so preventDefault is ignored and every zoom also
  // scrolled the page underneath. The ref keeps the listener reading the
  // current transform without re-attaching on every change.
  const transformRef = useRef(transform);
  transformRef.current = transform;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = svg!.getBoundingClientRect();
      const sx = ((event.clientX - rect.left) / rect.width) * WIDTH;
      const sy = ((event.clientY - rect.top) / rect.height) * HEIGHT;
      const current = transformRef.current;
      const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
      const k = Math.min(4, Math.max(0.25, current.k * factor));
      // Zoom around the pointer, not the corner.
      setTransform({
        k,
        x: sx - ((sx - current.x) / current.k) * k,
        y: sy - ((sy - current.y) / current.k) * k,
      });
    }

    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [data.nodes.length === 0]);

  const neighbours = useMemo(() => {
    const set = new Set<string>();
    if (!selectedId) return set;
    for (const rel of data.relationships) {
      if (rel.start === selectedId) set.add(rel.end);
      if (rel.end === selectedId) set.add(rel.start);
    }
    return set;
  }, [data, selectedId]);

  const labelsPresent = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of data.nodes) {
      const label = primaryLabel(node.labels);
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [data]);

  function toGraph(event: { clientX: number; clientY: number }): Point {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    const sx = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const sy = ((event.clientY - rect.top) / rect.height) * HEIGHT;
    return { x: (sx - transform.x) / transform.k, y: (sy - transform.y) / transform.k };
  }

  function onBackgroundDown(event: ReactPointerEvent<SVGRectElement>) {
    (event.target as Element).setPointerCapture(event.pointerId);
    setDrag({ kind: "pan", startX: event.clientX, startY: event.clientY, from: transform, moved: false });
  }

  function onNodeDown(event: ReactPointerEvent<SVGGElement>, id: string) {
    event.stopPropagation();
    (event.currentTarget as Element).setPointerCapture(event.pointerId);
    setDrag({ kind: "node", id, moved: false });
  }

  function onMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (!drag) return;

    if (drag.kind === "pan") {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const scale = WIDTH / rect.width;
      setTransform({
        ...drag.from,
        x: drag.from.x + (event.clientX - drag.startX) * scale,
        y: drag.from.y + (event.clientY - drag.startY) * scale,
      });
      if (!drag.moved) setDrag({ ...drag, moved: true });
      return;
    }

    const point = toGraph(event);
    setPositions((previous) => new Map(previous).set(drag.id, point));
    if (!drag.moved) setDrag({ ...drag, moved: true });
  }

  function onUp() {
    if (drag?.kind === "pan" && !drag.moved) onSelect(null);
    if (drag?.kind === "node" && !drag.moved) {
      const node = nodeById.get(drag.id) ?? null;
      onSelect(node && node.id === selectedId ? null : node);
    }
    setDrag(null);
  }

  if (data.nodes.length === 0) {
    return (
      <p className="graph-empty">
        Nothing to draw: the result has no nodes. Return nodes, relationships or paths
        (<code>RETURN a, r, b</code> or <code>RETURN p</code>), or switch to the table.
      </p>
    );
  }

  const captionAll = data.nodes.length < CAPTION_ALL_BELOW || transform.k > 1.6;

  // Zoomed out to fit a big result, text would shrink with everything
  // else until unreadable; below 1x it keeps its on-screen size instead.
  const textScale = 1 / Math.min(1, transform.k);
  const showRelLabels = data.relationships.length < 60 || transform.k > 1.8;

  return (
    <div className="graph-canvas">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Graph of ${data.nodes.length} nodes and ${data.relationships.length} relationships`}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={() => setDrag(null)}
      >
        <defs>
          <marker
            id="graph-arrow"
            viewBox="0 0 10 10"
            refX="10"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path className="graph-arrow-head" d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
        </defs>

        <rect
          className="graph-canvas-bg"
          width={WIDTH}
          height={HEIGHT}
          onPointerDown={onBackgroundDown}
        />

        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
          {data.relationships.map((rel) => {
            const a = positions.get(rel.start);
            const b = positions.get(rel.end);
            if (!a || !b) return null;

            const startNode = nodeById.get(rel.start);
            const endNode = nodeById.get(rel.end);
            const ra = LABEL_RADIUS[primaryLabel(startNode?.labels ?? [])] ?? 9;
            const rb = LABEL_RADIUS[primaryLabel(endNode?.labels ?? [])] ?? 9;

            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const d = Math.sqrt(dx * dx + dy * dy) || 1;

            // Stop at the circles' edges so the arrowhead is visible.
            const x1 = a.x + (dx / d) * ra;
            const y1 = a.y + (dy / d) * ra;
            const x2 = b.x - (dx / d) * (rb + 2);
            const y2 = b.y - (dy / d) * (rb + 2);

            const active = selectedId !== null && (rel.start === selectedId || rel.end === selectedId);
            const dim = selectedId !== null && !active;

            return (
              <g key={rel.id} className={dim ? "graph-rel is-dim" : active ? "graph-rel is-active" : "graph-rel"}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd="url(#graph-arrow)" />
                {(showRelLabels || active) && (
                  <text
                    x={(x1 + x2) / 2}
                    y={(y1 + y2) / 2 - 3}
                    textAnchor="middle"
                    style={{ fontSize: 7.5 * textScale }}
                  >
                    {rel.type}
                  </text>
                )}
              </g>
            );
          })}

          {data.nodes.map((node) => {
            const p = positions.get(node.id);
            if (!p) return null;

            const label = primaryLabel(node.labels);
            const r = LABEL_RADIUS[label] ?? 9;
            const selected = node.id === selectedId;
            const near = neighbours.has(node.id);
            const dim = selectedId !== null && !selected && !near;
            const caption =
              captionAll || selected || near || hovered === node.id || ALWAYS_CAPTIONED.has(label);

            return (
              <g
                key={node.id}
                className={`graph-node${selected ? " is-selected" : ""}${dim ? " is-dim" : ""}`}
                transform={`translate(${p.x} ${p.y})`}
                onPointerDown={(event) => onNodeDown(event, node.id)}
                onPointerEnter={() => setHovered(node.id)}
                onPointerLeave={() => setHovered(null)}
              >
                <circle r={r} fill={nodeColor(node)} />
                <title>{`${node.labels.join(":")}\n${nodeCaption(node)}`}</title>
                {caption && (
                  <text y={r + 11 * textScale} textAnchor="middle" style={{ fontSize: 10 * textScale }}>
                    {truncate(nodeCaption(node), selected ? 60 : 26)}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      <div className="graph-legend" aria-label="Legend">
        {labelsPresent.map(([label, count]) => (
          <span key={label} className="graph-legend-item">
            <span className="graph-swatch" style={{ background: LABEL_COLOR[label] ?? "var(--muted)" }} />
            {label} <span className="stats-muted">{count}</span>
          </span>
        ))}
        <span className="stats-muted graph-legend-hint">
          drag to pan · wheel to zoom · click a node
        </span>
        <button
          type="button"
          className="live-toggle"
          onClick={() => setTransform(fitTransform(positions))}
        >
          Fit to view
        </button>
      </div>
    </div>
  );
}
