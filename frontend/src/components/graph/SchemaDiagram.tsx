"use client";

import { LABEL_COLOR } from "@/lib/graphStyle";
import { GraphRelationshipDecl, GraphSchema } from "@/lib/types";

// Hand-placed rather than laid out: seven labels is few enough that a
// fixed picture reads better than a simulated one, and it stays the same
// picture every time the page opens. Articles at the top feed the claims
// below them; everything about provenance (evidence, sources) sits on the
// left, everything about meaning (entities, topics, verdicts) on the right.
const POSITIONS: Record<string, { x: number; y: number }> = {
  Article: { x: 330, y: 95 },
  Topic: { x: 600, y: 60 },
  Entity: { x: 640, y: 235 },
  Source: { x: 95, y: 235 },
  Claim: { x: 390, y: 330 },
  Verdict: { x: 640, y: 420 },
  Evidence: { x: 150, y: 430 },
};

const RADIUS = 38;
const WIDTH = 740;
const HEIGHT = 500;

export type SchemaSelection =
  | { kind: "node"; label: string }
  | { kind: "relationship"; rel: GraphRelationshipDecl };

export function relKey(rel: { from: string | null; type: string; to: string | null }) {
  return `${rel.from}-${rel.type}-${rel.to}`;
}

/**
 * The graph's schema as declared in backend/src/services/graph/schema.py,
 * with what the database actually holds on it: a count on every node and
 * every relationship. Click either for its description and properties.
 */
export function SchemaDiagram({
  schema,
  selected,
  onSelect,
}: {
  schema: GraphSchema;
  selected: SchemaSelection | null;
  onSelect: (selection: SchemaSelection | null) => void;
}) {
  const liveCounts = new Map(schema.live.patterns.map((p) => [relKey(p), p.count]));

  const isSelectedNode = (label: string) => selected?.kind === "node" && selected.label === label;
  const isSelectedRel = (rel: GraphRelationshipDecl) =>
    selected?.kind === "relationship" && relKey(selected.rel) === relKey(rel);

  return (
    <svg
      className="schema-diagram"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="Graph schema: node labels and the relationships between them"
    >
      <defs>
        <marker
          id="schema-arrow"
          viewBox="0 0 10 10"
          refX="10"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path className="schema-arrow-head" d="M 0 0 L 10 5 L 0 10 z" />
        </marker>
      </defs>

      <rect width={WIDTH} height={HEIGHT} fill="transparent" onClick={() => onSelect(null)} />

      {schema.relationships.map((rel) => {
        const a = POSITIONS[rel.from];
        const b = POSITIONS[rel.to];
        if (!a || !b) return null;

        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy);

        // A gentle curve, so the label sits beside the line rather than
        // on the node circles, and two edges into one node stay apart.
        const nx = -dy / d;
        const ny = dx / d;
        const bend = 22;
        const mx = (a.x + b.x) / 2 + nx * bend;
        const my = (a.y + b.y) / 2 + ny * bend;

        const start = { x: a.x + (dx / d) * RADIUS, y: a.y + (dy / d) * RADIUS };
        const end = { x: b.x - (dx / d) * (RADIUS + 3), y: b.y - (dy / d) * (RADIUS + 3) };

        const count = liveCounts.get(relKey(rel)) ?? 0;
        const active = isSelectedRel(rel);

        return (
          <g
            key={relKey(rel)}
            className={`schema-rel${active ? " is-selected" : ""}${count === 0 ? " is-empty" : ""}`}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(active ? null : { kind: "relationship", rel });
            }}
            role="button"
            tabIndex={0}
            aria-label={`${rel.from} ${rel.type} ${rel.to}: ${count}`}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSelect({ kind: "relationship", rel });
            }}
          >
            {/* Wide invisible stroke: a 1.5px line is too thin to click. */}
            <path
              className="schema-rel-hit"
              d={`M ${start.x} ${start.y} Q ${mx} ${my} ${end.x} ${end.y}`}
            />
            <path
              className="schema-rel-line"
              d={`M ${start.x} ${start.y} Q ${mx} ${my} ${end.x} ${end.y}`}
              markerEnd="url(#schema-arrow)"
            />
            <text x={(a.x + b.x) / 2 + nx * (bend / 2 + 6)} y={(a.y + b.y) / 2 + ny * (bend / 2 + 6)} textAnchor="middle">
              <tspan className="schema-rel-type">{rel.type}</tspan>
              <tspan className="schema-rel-count" dx="5">{count.toLocaleString()}</tspan>
            </text>
          </g>
        );
      })}

      {schema.nodes.map((node) => {
        const p = POSITIONS[node.label];
        if (!p) return null;

        const count = schema.live.labels[node.label] ?? 0;
        const active = isSelectedNode(node.label);

        return (
          <g
            key={node.label}
            className={`schema-node${active ? " is-selected" : ""}`}
            transform={`translate(${p.x} ${p.y})`}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(active ? null : { kind: "node", label: node.label });
            }}
            role="button"
            tabIndex={0}
            aria-label={`${node.label}: ${count} nodes`}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSelect({ kind: "node", label: node.label });
            }}
          >
            <circle r={RADIUS} style={{ fill: LABEL_COLOR[node.label] }} />
            <text className="schema-node-label" y={-2} textAnchor="middle">
              {node.label}
            </text>
            <text className="schema-node-count" y={15} textAnchor="middle">
              {count.toLocaleString()}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
