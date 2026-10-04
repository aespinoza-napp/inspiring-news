import { GROUP_NAMES, LABEL_NAMES } from "@/lib/evaluation";

// The fill stops below half strength so the count printed in every cell
// stays readable in --fg on both themes: one hue, more is darker, and
// the number - not the colour - carries the value.
const MIN_FILL = 8;
const MAX_FILL = 46;

function fill(count: number, perCell: number): string | undefined {
  if (count <= 0) return undefined;
  const share = Math.min(count / perCell, 1);
  const strength = Math.round(MIN_FILL + share * (MAX_FILL - MIN_FILL));
  return `color-mix(in oklch, var(--accent) ${strength}%, var(--surface))`;
}

/**
 * Verdict x topic group, against the labeller's target of `perCell`
 * facts a cell. A heatmap, because the job is "where is the set thin":
 * the empty and the full cells are what steer tomorrow's labelling.
 */
export function BalanceMatrix({
  labels,
  groups,
  matrix,
  perCell,
  byLabel,
  byGroup,
}: {
  labels: string[];
  groups: string[];
  matrix: Record<string, Record<string, number>>;
  perCell: number;
  byLabel: Record<string, number>;
  byGroup: Record<string, number>;
}) {
  const total = labels.reduce((sum, label) => sum + (byLabel[label] ?? 0), 0);
  const full = labels.reduce(
    (sum, label) =>
      sum + groups.filter((group) => (matrix[label]?.[group] ?? 0) >= perCell).length,
    0
  );

  return (
    <div className="eval-matrix-wrap">
      <table className="eval-matrix">
        <caption className="eval-caption">
          Facts per verdict and topic group. Target {perCell} a cell;{" "}
          {full} of {labels.length * groups.length} cells are full.
        </caption>
        <thead>
          <tr>
            <th scope="col">Verdict</th>
            {groups.map((group) => (
              <th key={group} scope="col">
                {GROUP_NAMES[group] ?? group}
              </th>
            ))}
            <th scope="col" className="eval-matrix-total">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {labels.map((label) => (
            <tr key={label}>
              <th scope="row">
                <span className={`badge badge-${label.toLowerCase()}`}>
                  {LABEL_NAMES[label] ?? label}
                </span>
              </th>
              {groups.map((group) => {
                const count = matrix[label]?.[group] ?? 0;
                const done = count >= perCell;
                return (
                  <td
                    key={group}
                    className={done ? "eval-cell eval-cell-full" : "eval-cell"}
                    style={{ background: fill(count, perCell) }}
                    title={`${LABEL_NAMES[label] ?? label} · ${GROUP_NAMES[group] ?? group}: ${count} of ${perCell}${done ? " (full)" : ""}`}
                  >
                    {count}
                    {done && <span className="eval-cell-mark" aria-label="full"> ✓</span>}
                  </td>
                );
              })}
              <td className="eval-matrix-total">{byLabel[label] ?? 0}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            {groups.map((group) => (
              <td key={group} className="eval-matrix-total">
                {byGroup[group] ?? 0}
              </td>
            ))}
            <td className="eval-matrix-total">{total}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
