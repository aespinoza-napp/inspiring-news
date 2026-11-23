// Which point is under the pointer: a uniform grid over the points,
// built once per data set, so a hover looks at a few cells rather than
// every point (docs/goals.md, N8: picking under 4 ms at 10k).

export class SpatialGrid {
  private readonly cells = new Map<number, number[]>();
  private readonly minX: number;
  private readonly minY: number;
  private readonly columns: number;

  constructor(private readonly positions: Float32Array, private readonly cell: number) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;

    for (let i = 0; i < positions.length; i += 2) {
      minX = Math.min(minX, positions[i]);
      maxX = Math.max(maxX, positions[i]);
      minY = Math.min(minY, positions[i + 1]);
    }

    this.minX = Number.isFinite(minX) ? minX : 0;
    this.minY = Number.isFinite(minY) ? minY : 0;
    this.columns = Math.max(1, Math.ceil(((Number.isFinite(maxX) ? maxX : 0) - this.minX) / cell) + 1);

    for (let i = 0; i < positions.length / 2; i++) {
      const key = this.key(positions[i * 2], positions[i * 2 + 1]);
      const bucket = this.cells.get(key);
      if (bucket) bucket.push(i);
      else this.cells.set(key, [i]);
    }
  }

  private column(x: number): number {
    return Math.floor((x - this.minX) / this.cell);
  }

  private row(y: number): number {
    return Math.floor((y - this.minY) / this.cell);
  }

  private key(x: number, y: number): number {
    return this.row(y) * this.columns + this.column(x);
  }

  // The nearest point within `radius` (map units) of (x, y) that `accept`
  // lets through, or -1.
  nearest(x: number, y: number, radius: number, accept?: (index: number) => boolean): number {
    const reach = Math.ceil(radius / this.cell);
    const column = this.column(x);
    const row = this.row(y);

    let best = -1;
    let bestDistance = radius * radius;

    for (let r = row - reach; r <= row + reach; r++) {
      for (let c = column - reach; c <= column + reach; c++) {
        if (c < 0 || c >= this.columns) continue;
        const bucket = this.cells.get(r * this.columns + c);
        if (!bucket) continue;

        for (const index of bucket) {
          const dx = this.positions[index * 2] - x;
          const dy = this.positions[index * 2 + 1] - y;
          const distance = dx * dx + dy * dy;
          if (distance <= bestDistance && (!accept || accept(index))) {
            best = index;
            bestDistance = distance;
          }
        }
      }
    }

    return best;
  }
}
