/**
 * A small Fruchterman-Reingold layout for the /graph page's result view.
 *
 * Hand-written rather than a dependency: the frontend takes nothing
 * beyond next/react/react-dom (frontend/CLAUDE.md), and a few hundred
 * nodes is well within what a plain O(n^2) repulsion pass can settle in
 * one synchronous run.
 *
 * Deterministic on purpose - starting positions come from a golden-angle
 * spiral over the input order, not Math.random - so running the same
 * query twice draws the same picture, and a node you found once is where
 * you left it.
 */

export interface Point {
  x: number;
  y: number;
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

export function forceLayout(
  ids: string[],
  edges: [string, string][],
  width: number,
  height: number,
  fixed: Map<string, Point> = new Map()
): Map<string, Point> {
  const n = ids.length;
  const positions = new Map<string, Point>();

  if (n === 0) return positions;

  const cx = width / 2;
  const cy = height / 2;

  const xs = new Float64Array(n);
  const ys = new Float64Array(n);
  const pinned = new Uint8Array(n);
  const index = new Map<string, number>();

  const spread = Math.min(width, height) * 0.42;

  ids.forEach((id, i) => {
    index.set(id, i);
    const kept = fixed.get(id);
    if (kept) {
      xs[i] = kept.x;
      ys[i] = kept.y;
      pinned[i] = 1;
    } else {
      const r = spread * Math.sqrt((i + 0.5) / n);
      xs[i] = cx + r * Math.cos(i * GOLDEN_ANGLE);
      ys[i] = cy + r * Math.sin(i * GOLDEN_ANGLE);
    }
  });

  const links: [number, number][] = [];
  for (const [a, b] of edges) {
    const ia = index.get(a);
    const ib = index.get(b);
    if (ia !== undefined && ib !== undefined && ia !== ib) links.push([ia, ib]);
  }

  // Ideal edge length: the area shared out between the nodes.
  const k = Math.max(28, Math.sqrt((width * height) / n) * 0.75);
  const k2 = k * k;

  // Fewer passes for big results: repulsion is quadratic.
  const iterations = n > 250 ? 120 : n > 120 ? 200 : 300;

  const dx = new Float64Array(n);
  const dy = new Float64Array(n);

  for (let iter = 0; iter < iterations; iter++) {
    const temperature = (width / 8) * (1 - iter / iterations) + 0.5;

    dx.fill(0);
    dy.fill(0);

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let ddx = xs[i] - xs[j];
        let ddy = ys[i] - ys[j];
        let d2 = ddx * ddx + ddy * ddy;
        if (d2 < 0.01) {
          // Two nodes on the same spot: nudge apart along a fixed axis.
          ddx = 0.1 * ((i % 3) - 1 || 1);
          ddy = 0.1;
          d2 = 0.02;
        }
        const force = k2 / d2;
        dx[i] += ddx * force;
        dy[i] += ddy * force;
        dx[j] -= ddx * force;
        dy[j] -= ddy * force;
      }
    }

    for (const [a, b] of links) {
      const ddx = xs[a] - xs[b];
      const ddy = ys[a] - ys[b];
      const d = Math.sqrt(ddx * ddx + ddy * ddy) || 0.01;
      const force = d / k;
      dx[a] -= ddx * force;
      dy[a] -= ddy * force;
      dx[b] += ddx * force;
      dy[b] += ddy * force;
    }

    for (let i = 0; i < n; i++) {
      if (pinned[i]) continue;

      // Gravity: keeps disconnected pieces on screen.
      dx[i] -= (xs[i] - cx) * 0.02 * k;
      dy[i] -= (ys[i] - cy) * 0.02 * k;

      const d = Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]) || 1;
      const step = Math.min(d, temperature);
      xs[i] += (dx[i] / d) * step;
      ys[i] += (dy[i] / d) * step;
    }
  }

  ids.forEach((id, i) => positions.set(id, { x: xs[i], y: ys[i] }));

  return positions;
}
