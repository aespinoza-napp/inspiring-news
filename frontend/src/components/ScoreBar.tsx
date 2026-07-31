export function ScoreBar({
  label,
  value,
  max = 100,
}: {
  label: string;
  value: number;
  max?: number;
}) {
  const percent = Math.max(0, Math.min((value / max) * 100, 100));

  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <span className="score-bar-track">
        <span className="score-bar-fill" style={{ width: `${percent}%` }} />
      </span>
      <span className="score-bar-value">{Math.round(value)}</span>
    </div>
  );
}
