import { SelectionBatch, percent } from "@/lib/evaluation";

const PARTS = [
  { key: "labelled", label: "Labelled", className: "eval-seg-labelled" },
  { key: "skipped", label: "Skipped", className: "eval-seg-skipped" },
  { key: "pending", label: "Not judged yet", className: "eval-seg-pending" },
] as const;

function shortDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/**
 * What became of the claims the pipeline proposed, one daily batch a
 * row. Emphasis rather than three hues: what was labelled is the accent,
 * what was skipped is grey, what nobody has judged is an outline - so
 * the eye reads "how much of it was worth checking" first.
 */
export function SelectionChart({ batches }: { batches: SelectionBatch[] }) {
  const max = Math.max(1, ...batches.map((batch) => batch.proposed));

  return (
    <div className="eval-selection">
      <div className="eval-legend" aria-hidden="true">
        {PARTS.map((part) => (
          <span key={part.key} className="eval-legend-item">
            <span className={`eval-legend-swatch ${part.className}`} />
            {part.label}
          </span>
        ))}
      </div>

      <ul className="eval-stack-list" aria-label="Claims proposed per daily batch">
        {batches.map((batch) => {
          const judged = batch.labelled + batch.skipped;
          const summary = `${batch.file}: ${batch.proposed} proposed, ${batch.labelled} labelled, ${batch.skipped} skipped, ${batch.pending} not judged`;
          return (
            <li key={batch.file} className="eval-stack-row" title={summary}>
              <span className="eval-bar-label">{shortDate(batch.date)}</span>
              <span className="eval-stack-track" aria-label={summary}>
                {PARTS.map((part) => {
                  const value = batch[part.key];
                  if (value <= 0) return null;
                  return (
                    <span
                      key={part.key}
                      className={`eval-seg ${part.className}`}
                      style={{ width: `${(value / max) * 100}%` }}
                      title={`${part.label}: ${value}`}
                    />
                  );
                })}
              </span>
              <span className="eval-bar-value">
                {batch.labelled}/{judged || 0}
                <span className="eval-bar-note"> {judged ? percent(batch.labelled / judged) : ""}</span>
              </span>
            </li>
          );
        })}
      </ul>

      <details className="eval-table-toggle">
        <summary>As a table</summary>
        <table className="eval-small-table">
          <thead>
            <tr>
              <th scope="col">Batch</th>
              <th scope="col">Articles</th>
              <th scope="col">Proposed</th>
              <th scope="col">Labelled</th>
              <th scope="col">Skipped</th>
              <th scope="col">Not judged</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.file}>
                <td>{batch.file.replace(/\.json$/, "")}</td>
                <td>{batch.articles}</td>
                <td>{batch.proposed}</td>
                <td>{batch.labelled}</td>
                <td>{batch.skipped}</td>
                <td>{batch.pending}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
