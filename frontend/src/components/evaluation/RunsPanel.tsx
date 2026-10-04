"use client";

import { useState } from "react";
import {
  Estimate,
  HarnessRun,
  LABEL_NAMES,
  asEstimate,
  asNumber,
  asRecord,
  percent,
  pick,
} from "@/lib/evaluation";

// metrics.json is the harness's own format (docs/decisions/evaluation.md
// §Metrics). These are the paths tried for each figure, first match wins,
// so a renamed key in the harness shows as "–" here rather than breaking
// the page.
const ACCURACY = ["accuracy", "overall.accuracy", "scored.accuracy", "metrics.accuracy"];
const MACRO_F1 = ["macroF1", "macro_f1", "overall.macroF1", "scored.macroF1", "metrics.macroF1"];
const COVERAGE = ["coverage", "overall.coverage", "scored.coverage"];
const SCORED = ["n", "scored", "counts.scored", "overall.n", "total"];
const CONFUSION = ["confusion", "confusionMatrix", "overall.confusion", "scored.confusion"];

function Interval({ estimate }: { estimate: Estimate | null }) {
  if (!estimate) return <span className="eval-muted">–</span>;

  const { value, low, high } = estimate;
  const hasCi = low !== null && high !== null;

  return (
    <span
      className="eval-ci"
      title={hasCi ? `${percent(value, 1)} (95% CI ${percent(low, 1)} – ${percent(high, 1)})` : percent(value, 1)}
    >
      <span className="eval-ci-value">{percent(value, 1)}</span>
      {hasCi && (
        <span className="eval-ci-track" aria-hidden="true">
          <span
            className="eval-ci-range"
            style={{ left: `${(low as number) * 100}%`, width: `${((high as number) - (low as number)) * 100}%` }}
          />
          <span className="eval-ci-dot" style={{ left: `${value * 100}%` }} />
        </span>
      )}
    </span>
  );
}

/**
 * gold -> predicted -> count, from either a nested object or
 * {labels, matrix}. Anything else is not drawn.
 */
function readConfusion(value: unknown): { labels: string[]; cell: (g: string, p: string) => number } | null {
  const record = asRecord(value);
  if (!record) return null;

  if (Array.isArray(record.labels) && Array.isArray(record.matrix)) {
    const labels = record.labels.map(String);
    const rows = record.matrix as unknown[];
    return {
      labels,
      cell: (g, p) => {
        const row = rows[labels.indexOf(g)];
        return Array.isArray(row) ? asNumber(row[labels.indexOf(p)]) ?? 0 : 0;
      },
    };
  }

  const labels = Object.keys(record);
  if (labels.length === 0 || !labels.every((l) => asRecord(record[l]))) return null;
  const predicted = Array.from(new Set(labels.flatMap((l) => Object.keys(asRecord(record[l]) ?? {}))));
  const all = Array.from(new Set([...labels, ...predicted]));
  return {
    labels: all,
    cell: (g, p) => asNumber(asRecord(record[g])?.[p]) ?? 0,
  };
}

function Confusion({ value }: { value: unknown }) {
  const confusion = readConfusion(value);
  if (!confusion) return null;

  const max = Math.max(
    1,
    ...confusion.labels.flatMap((g) => confusion.labels.map((p) => confusion.cell(g, p)))
  );

  return (
    <div className="eval-matrix-wrap">
      <table className="eval-matrix">
        <caption className="eval-caption">
          Confusion matrix: rows are the gold label, columns the model&apos;s verdict. The diagonal is right.
        </caption>
        <thead>
          <tr>
            <th scope="col">Gold ↓ / model →</th>
            {confusion.labels.map((p) => (
              <th key={p} scope="col">
                {LABEL_NAMES[p] ?? p}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {confusion.labels.map((g) => (
            <tr key={g}>
              <th scope="row">{LABEL_NAMES[g] ?? g}</th>
              {confusion.labels.map((p) => {
                const count = confusion.cell(g, p);
                const strength = count > 0 ? Math.round(8 + (count / max) * 38) : 0;
                return (
                  <td
                    key={p}
                    className={g === p ? "eval-cell eval-cell-diagonal" : "eval-cell"}
                    style={{
                      background: count > 0
                        ? `color-mix(in oklch, var(--accent) ${strength}%, var(--surface))`
                        : undefined,
                    }}
                    title={`Gold ${LABEL_NAMES[g] ?? g}, model ${LABEL_NAMES[p] ?? p}: ${count}`}
                  >
                    {count}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The evaluation harness's runs, newest first. Before the harness has
 * run, says how to run it rather than showing an empty table.
 */
export function RunsPanel({ runs }: { runs: HarnessRun[] }) {
  const [selected, setSelected] = useState(0);

  if (runs.length === 0) {
    return (
      <div className="eval-empty">
        <p>
          No model run yet. Once the harness has run over a labelled set, its reports land in{" "}
          <code>backend/data/evaluation/reports/&lt;dataset&gt;/&lt;model&gt;/&lt;key&gt;/</code> and show
          here: accuracy and macro-F1 with their confidence intervals, coverage, and the confusion matrix
          against the gold labels.
        </p>
        <p className="eval-muted">
          See <code>docs/decisions/evaluation.md</code> for how to run it.
        </p>
      </div>
    );
  }

  const current = runs[Math.min(selected, runs.length - 1)];

  return (
    <div>
      <div className="stats-table-wrap eval-runs-wrap">
        <table className="stats-table eval-runs">
          <thead>
            <tr>
              <th scope="col">Dataset</th>
              <th scope="col">Model</th>
              <th scope="col">Scored</th>
              <th scope="col">Accuracy</th>
              <th scope="col">Macro-F1</th>
              <th scope="col">Coverage</th>
              <th scope="col">When</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run, index) => (
              <tr
                key={`${run.dataset}/${run.model}/${run.key}`}
                className={index === selected ? "eval-run-selected" : undefined}
              >
                <td>
                  <button type="button" className="eval-link-button" onClick={() => setSelected(index)}>
                    {run.dataset}
                  </button>
                </td>
                <td>{run.model}</td>
                <td>{asNumber(pick(run.metrics, ...SCORED)) ?? "–"}</td>
                <td>
                  <Interval estimate={asEstimate(pick(run.metrics, ...ACCURACY))} />
                </td>
                <td>
                  <Interval estimate={asEstimate(pick(run.metrics, ...MACRO_F1))} />
                </td>
                <td>{percent(asNumber(pick(run.metrics, ...COVERAGE)))}</td>
                <td className="eval-muted">
                  {new Date(run.modifiedAt * 1000).toLocaleDateString()}
                  {run.error && <span className="stats-bad"> · {run.error}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="section-label">
        {current.dataset} · {current.model}
        <span className="section-label-note">{current.key}</span>
      </p>
      <Confusion value={pick(current.metrics, ...CONFUSION)} />

      <details className="eval-table-toggle">
        <summary>metrics.json as written</summary>
        <pre className="eval-json">{JSON.stringify(current.metrics, null, 2)}</pre>
      </details>
    </div>
  );
}
