"use client";

import { useEffect, useRef, useState } from "react";

export interface DailyPoint {
  date: string;
  value: number;
}

// Geometry in real pixels: the SVG is drawn at its container's measured
// width, not stretched to it, so corners stay round and lines stay 1px.
const HEIGHT = 140;
const TOP = 12;
const BOTTOM = 1;
const GAP = 2;
const RADIUS = 4;

/**
 * A rounded top on a bar anchored to the baseline: square at the axis,
 * 4px radius at the data end.
 */
function barPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, width / 2, height);
  const base = y + height;

  return [
    `M${x},${base}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${base}`,
    "Z",
  ].join(" ");
}

function shortDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/**
 * One series of daily counts as bars. One colour (`--series-1`), no
 * legend - the section title names the series - a tooltip per bar, and
 * the same numbers as a table for anyone who cannot read the bars.
 */
export function DailyBars({
  points,
  unit,
  label,
}: {
  points: DailyPoint[];
  /** Singular/plural noun for the tooltip, e.g. ["article", "articles"]. */
  unit: [string, string];
  /** Accessible name for the chart. */
  label: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [width, setWidth] = useState(600);
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = plotRef.current;
    if (!element) return;

    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(Math.floor(entry.contentRect.width), 120));
    });

    observer.observe(element);
    return () => observer.disconnect();
    // Re-run once there is data: with none, the plot is not rendered and
    // the ref is empty, so an effect that ran only on mount would never
    // start measuring.
  }, [points.length > 0]);

  if (points.length === 0) {
    return <p className="claims-note">Nothing scraped yet.</p>;
  }

  const max = Math.max(...points.map((point) => point.value), 1);
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const slot = width / points.length;
  // Capped: five days across a wide card would otherwise be five slabs.
  const barWidth = Math.min(Math.max(slot - GAP, 1), 48);

  const active = hovered !== null ? points[hovered] : null;

  return (
    <div className="daily-bars">
      <div className="daily-bars-plot" ref={plotRef}>
        <svg
          width={width}
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          role="img"
          aria-label={label}
          onMouseLeave={() => setHovered(null)}
        >
          {/* Baseline only: counts start at zero and the tooltip and
              table carry exact values, so a grid would add nothing. */}
          <line
            className="daily-bars-axis"
            x1={0}
            x2={width}
            y1={HEIGHT - BOTTOM}
            y2={HEIGHT - BOTTOM}
          />

          {points.map((point, index) => {
            const height = (point.value / max) * plotHeight;
            const x = index * slot + (slot - barWidth) / 2;
            const y = HEIGHT - BOTTOM - height;

            return (
              <g key={point.date}>
                {point.value > 0 && (
                  <path
                    className={
                      hovered === null || hovered === index
                        ? "daily-bars-bar"
                        : "daily-bars-bar is-dimmed"
                    }
                    d={barPath(x, y, barWidth, height)}
                  />
                )}
                {/* The hit target is the whole column, not the bar: a
                    one-article day is a sliver nobody could point at. */}
                <rect
                  className="daily-bars-hit"
                  x={index * slot}
                  y={0}
                  width={slot}
                  height={HEIGHT - BOTTOM}
                  tabIndex={0}
                  aria-label={`${shortDate(point.date)}: ${point.value} ${
                    point.value === 1 ? unit[0] : unit[1]
                  }`}
                  onMouseEnter={() => setHovered(index)}
                  onFocus={() => setHovered(index)}
                  onBlur={() => setHovered(null)}
                />
              </g>
            );
          })}
        </svg>

        {active && hovered !== null && (
          <div
            className="daily-bars-tooltip"
            style={{
              left: `${((hovered + 0.5) / points.length) * 100}%`,
            }}
            role="status"
          >
            <strong>{active.value}</strong>{" "}
            {active.value === 1 ? unit[0] : unit[1]}
            <span>{shortDate(active.date)}</span>
          </div>
        )}
      </div>

      {/* Selective labels: the first and last day and the busiest one,
          never a label under every bar. */}
      <div className="daily-bars-labels" aria-hidden="true">
        <span>{shortDate(points[0].date)}</span>
        <span>
          busiest {max} on{" "}
          {shortDate(points.find((point) => point.value === max)!.date)}
        </span>
        <span>{shortDate(points[points.length - 1].date)}</span>
      </div>

      <details className="daily-bars-table">
        <summary>Show as table</summary>
        <table>
          <thead>
            <tr>
              <th>Day</th>
              <th>{unit[1]}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.date}>
                <td>{point.date}</td>
                <td>{point.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
