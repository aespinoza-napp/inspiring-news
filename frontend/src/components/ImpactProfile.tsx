import { CSSProperties } from "react";
import { QualityScores } from "@/lib/types";

type Dimension = keyof QualityScores;

// Grouped by how much each dimension counts in the admission filter's
// positive-impact score (backend/src/services/admission/positive_impact.py):
// constructiveness, inspiration and hopefulness weigh 1.0 each of the 3.5
// the score is divided by; societal impact 0.15, objectivity and
// readability 0.10; novelty is not in it. The grouping is what this panel
// explains, so if those weights move, move the rows with them.
const GROUPS: { label: string; note: string; rows: { key: Dimension; label: string }[] }[] = [
  {
    label: "Drive the score",
    note: "most of it",
    rows: [
      { key: "constructiveness", label: "Constructive" },
      { key: "inspirationalScore", label: "Inspiring" },
      { key: "hopefulness", label: "Hopeful" },
    ],
  },
  {
    label: "Adjust it",
    note: "a little each",
    rows: [
      { key: "societalImpact", label: "Societal impact" },
      { key: "objectivity", label: "Objective" },
      { key: "readability", label: "Readable" },
    ],
  },
  {
    label: "Not in the score",
    note: "",
    rows: [{ key: "novelty", label: "Novel" }],
  },
];

// The filter's own reasons, as it words them, mapped back to the row they
// are about. Any other reason is still listed under the meter.
const FLAGGED_BY: Record<string, Dimension> = {
  "Low constructiveness": "constructiveness",
  "Low inspirational value": "inspirationalScore",
  "Low objectivity": "objectivity",
};

function percent(value: number): number {
  return Math.round(Math.max(0, Math.min(value, 1)) * 100);
}

/**
 * The positive-impact score first - the one number the admission filter
 * gates on, with the run's minimum marked on its meter - and then the
 * quality dimensions it is made of, grouped by how much each counts. The
 * radar this replaced drew seven unordered axes whose shape depended on
 * their order around the circle; bars on one 0-100 scale compare
 * directly, and the grouping says why some matter more than others.
 */
export function ImpactProfile({
  quality,
  score,
  minimum,
  reasons = [],
}: {
  quality: QualityScores;
  /** validity.impactScore, once admission has run. */
  score?: number;
  /** The run's positive_impact_min_score. */
  minimum?: number;
  reasons?: string[];
}) {
  const flagged = new Set(
    reasons.map((reason) => FLAGGED_BY[reason]).filter(Boolean)
  );
  const unmapped = reasons.filter(
    (reason) => !FLAGGED_BY[reason] && reason !== "Strong negative sentiment"
  );

  const passes = score != null && minimum != null ? score >= minimum : null;

  const meterStyle = {
    "--fill": `${percent(score ?? 0)}%`,
    "--minimum": `${percent(minimum ?? 0)}%`,
  } as CSSProperties;

  return (
    <div className="impact">
      {score != null && (
        <div className="impact-score">
          <div className="impact-score-head">
            <span className="impact-score-value">{percent(score)}</span>
            <span className="impact-score-unit">/ 100 positive impact</span>
            {passes != null && (
              <span className={`impact-status ${passes ? "is-pass" : "is-fail"}`}>
                <span className="impact-status-dot" aria-hidden="true" />
                {passes ? "Clears" : "Below"} the minimum of {percent(minimum ?? 0)}
              </span>
            )}
          </div>
          <div
            className={`impact-meter${minimum != null ? " has-minimum" : ""}`}
            style={meterStyle}
            role="meter"
            aria-label="Positive-impact score"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent(score)}
          >
            <span className="impact-meter-fill" />
          </div>
          {unmapped.length > 0 && (
            <p className="trace-muted impact-reasons">{unmapped.join(" · ")}</p>
          )}
        </div>
      )}

      {GROUPS.map((group, weight) => (
        <div className={`impact-group impact-weight-${weight}`} key={group.label}>
          <div className="impact-group-label">
            {group.label}
            {group.note && <span> · {group.note}</span>}
          </div>
          {group.rows.map((row) => {
            const value = percent(quality[row.key]);
            const isFlagged = flagged.has(row.key);

            return (
              <div className="impact-row" key={row.key}>
                <span className="impact-row-label">
                  {row.label}
                  {isFlagged && <span className="impact-flag">flagged low</span>}
                </span>
                <span className="impact-row-track">
                  <span
                    className="impact-row-fill"
                    style={{ width: `${value}%` }}
                    title={`${row.label}: ${value}/100`}
                  />
                </span>
                <span className="impact-row-value">{value}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
