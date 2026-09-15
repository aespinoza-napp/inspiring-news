export function ScoreBar({
  label,
  value,
  max = 100,
  color,
  swatch = false,
  showValue = true,
}: {
  label: string;
  value: number;
  max?: number;
  /** Overrides the default single accent fill - for a set of bars that
   *  need an identity color each (e.g. topics), not for a single-series
   *  magnitude bar (leave unset - it stays the default accent hue). */
  color?: string;
  /** Shows a small color dot before the label, so the color reads as
   *  identity even before the bar itself is scanned. */
  swatch?: boolean;
  /** Hides the trailing number - for rows where the bar length itself
   *  is meant to carry the value (e.g. keyword representation), and a
   *  raw score would just repeat what the length already shows. */
  showValue?: boolean;
}) {
  const percent = Math.max(0, Math.min((value / max) * 100, 100));

  return (
    <div className="score-bar-row">
      {swatch && (
        <span className="score-bar-swatch" style={{ background: color }} aria-hidden="true" />
      )}
      <span className="score-bar-label">{label}</span>
      <span
        className="score-bar-track"
        role="progressbar"
        aria-label={label}
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span
          className="score-bar-fill"
          style={{ width: `${percent}%`, background: color }}
        />
      </span>
      {showValue && <span className="score-bar-value">{Math.round(value)}</span>}
    </div>
  );
}
