import { seriesColor } from "@/lib/palette";

export interface RadarAxis {
  key: string;
  label: string;
  /** 0-1. Values outside that range are clamped. */
  value: number;
  /** Palette slot to color this axis with - defaults to its position in
   *  `axes` when omitted. Lets a caller keep one stable identity color
   *  per item across charts (e.g. topics, whose radar shares a fixed
   *  canonical order with the keyword breakdown shown next to it)
   *  instead of a plain per-position palette cycle that would only
   *  match by coincidence. */
  colorIndex?: number;
}

const CENTER = 100;
const RADIUS = 75;
const LABEL_RADIUS = 92;
const RINGS = [0.25, 0.5, 0.75, 1];

// The viewBox is padded well beyond the 0-200 box the geometry below is
// drawn in: a start/end-anchored label at LABEL_RADIUS sits right at
// x=8 or x=192, and its own text then extends further outward from
// there - clipped to nothing ("Hopeful" rendering as "Hoi") without
// this margin. `overflow: visible` alone isn't enough because sibling
// layout still positions against the un-padded box. This is a
// *coordinate-space* clip, independent of how large the SVG renders in
// CSS pixels - a wider container never fixes it, only more viewBox
// margin (or a shorter label - see MAX_CHART_LABEL_LENGTH) does.
const VIEWBOX_PAD = 60;
const VIEWBOX = `${-VIEWBOX_PAD} ${-VIEWBOX_PAD} ${200 + VIEWBOX_PAD * 2} ${200 + VIEWBOX_PAD * 2}`;

// Quality's axis labels are hand-picked short words ("Constructive",
// "Objective") and always fit. Topic names come straight from
// src/config/topics.py and are not chart-sized ("Community & Social
// Impact" is 26 characters) - truncated here for the on-chart label
// only, with the full name still in the legend and the hover title.
const MAX_CHART_LABEL_LENGTH = 12;

function shortLabel(label: string): string {
  return label.length > MAX_CHART_LABEL_LENGTH
    ? label.slice(0, MAX_CHART_LABEL_LENGTH).trimEnd()
    : label;
}

// The data polygon's fill blends a few slots from the same fixed
// categorical order the vertices use, picked for hue contrast
// (blue/orange/magenta) so it reads as multicolor rather than a flat
// wash - three adjacent hues (e.g. blue/aqua/green) blend into one flat
// teal instead.
const GRADIENT_STOPS = [0, 1, 4] as const;

function point(index: number, count: number, ratio: number, radius: number = RADIUS) {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  return {
    x: CENTER + radius * ratio * Math.cos(angle),
    y: CENTER + radius * ratio * Math.sin(angle),
  };
}

function polygonPoints(count: number, ratios: number[]): string {
  return ratios.map((ratio, index) => {
    const { x, y } = point(index, count, ratio);
    return `${x},${y}`;
  }).join(" ");
}

/**
 * N labeled dimensions on one chart instead of N separate bars a reader
 * has to scan and compare one at a time - a radar reads the overall
 * shape at a glance. Shared by the quality-score chart (7 fixed axes)
 * and the top-topics chart (up to 5, article-dependent) - the geometry,
 * label-clipping fix and color assignment are identical, only the axis
 * count and data source differ.
 *
 * Each axis gets its own identity color from the shared categorical
 * palette (spoke, vertex and label all match), and a `legendColumns`
 * layout to fit a 7-axis and a <=5-axis chart differently.
 */
export function RadarChart({
  axes,
  ariaLabel,
  legendColumns = 2,
  gradientId,
}: {
  axes: RadarAxis[];
  ariaLabel: string;
  legendColumns?: 1 | 2;
  /** Unique per chart instance - multiple radars on one page must not
   *  share an SVG <defs> id. */
  gradientId: string;
}) {
  const count = axes.length;
  const values = axes.map((axis) => Math.max(0, Math.min(axis.value, 1)));

  if (count === 0) {
    return null;
  }

  return (
    <div className="radar">
      <svg viewBox={VIEWBOX} className="radar-svg" role="img" aria-label={ariaLabel}>
        <defs>
          <radialGradient id={gradientId} cx="50%" cy="50%" r="65%">
            {GRADIENT_STOPS.map((axisIndex, stopIndex) => (
              <stop
                key={axisIndex}
                offset={`${(stopIndex / (GRADIENT_STOPS.length - 1)) * 100}%`}
                stopColor={seriesColor(axisIndex)}
                stopOpacity={0.4}
              />
            ))}
          </radialGradient>
        </defs>

        {count >= 3 && RINGS.map((ratio) => (
          <polygon
            key={ratio}
            points={polygonPoints(count, axes.map(() => ratio))}
            className="radar-ring"
          />
        ))}
        {axes.map((axis, index) => {
          const { x, y } = point(index, count, 1);
          return (
            <line
              key={axis.key}
              x1={CENTER}
              y1={CENTER}
              x2={x}
              y2={y}
              className="radar-axis"
              style={{ stroke: seriesColor(axis.colorIndex ?? index) }}
            />
          );
        })}
        {count >= 3 ? (
          <polygon points={polygonPoints(count, values)} className="radar-shape" fill={`url(#${gradientId})`} />
        ) : (
          // A 1- or 2-axis "polygon" is degenerate (a point or a line) -
          // there's no area to fill, so the spokes and vertices alone
          // carry the shape instead of an invisible fill.
          <polyline
            points={polygonPoints(count, values)}
            className="radar-shape"
            fill="none"
          />
        )}
        {axes.map((axis, index) => {
          const { x, y } = point(index, count, values[index]);
          return (
            <circle
              key={axis.key}
              cx={x}
              cy={y}
              r="4"
              className="radar-vertex"
              style={{ fill: seriesColor(axis.colorIndex ?? index) }}
            >
              <title>{axis.label}: {Math.round(values[index] * 100)}%</title>
            </circle>
          );
        })}
        {axes.map((axis, index) => {
          const { x, y } = point(index, count, 1, LABEL_RADIUS);
          const anchor = x < CENTER - 2 ? "end" : x > CENTER + 2 ? "start" : "middle";
          return (
            <text
              key={axis.key}
              x={x}
              y={y}
              textAnchor={anchor}
              className="radar-label"
              style={{ fill: seriesColor(axis.colorIndex ?? index) }}
            >
              {shortLabel(axis.label)}
              {axis.label.length > MAX_CHART_LABEL_LENGTH && "…"}
            </text>
          );
        })}
      </svg>
      <dl className={`radar-legend radar-legend-cols-${legendColumns}`}>
        {axes.map((axis, index) => (
          <div className="radar-legend-row" key={axis.key}>
            <dt>
              <span
                className="radar-legend-swatch"
                style={{ background: seriesColor(axis.colorIndex ?? index) }}
                aria-hidden="true"
              />
              {axis.label}
            </dt>
            <dd>{Math.round(values[index] * 100)}%</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
