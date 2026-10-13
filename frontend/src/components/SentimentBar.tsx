import { SentimentScores } from "@/lib/types";

const SEGMENTS = [
  { key: "negative", label: "Negative" },
  { key: "neutral", label: "Neutral" },
  { key: "positive", label: "Positive" },
] as const;

/**
 * The classifier's three shares as one bar, negative to positive, instead
 * of a needle on a red-amber-green track. The needle showed only polarity
 * (positive minus negative), so an article that was 45% positive and 45%
 * negative read the same as one that was all neutral; the shares show
 * which it is. The colors are a diverging pair with a gray middle, not
 * the verdict colors: sentiment is not a judgement of truth.
 *
 * Every share is also written out beside its swatch, so the bar never has
 * to be read by color alone (the light gray clears 2:1, not 3:1).
 */
export function SentimentBar({
  sentiment,
  flagged = false,
}: {
  sentiment: SentimentScores;
  /** The admission filter reported "Strong negative sentiment". */
  flagged?: boolean;
}) {
  const raw = SEGMENTS.map((segment) => Math.max(0, sentiment[segment.key]));
  const total = raw.reduce((sum, value) => sum + value, 0) || 1;
  const shares = raw.map((value) => value / total);

  const label = sentiment.label
    ? sentiment.label.charAt(0).toUpperCase() + sentiment.label.slice(1).toLowerCase()
    : "Neutral";

  const summary = SEGMENTS.map(
    (segment, index) => `${segment.label} ${Math.round(shares[index] * 100)}%`
  ).join(", ");

  return (
    <div className="sentiment">
      <div className="sentiment-head">
        <span className="sentiment-label">{label}</span>
        <span className="sentiment-meta">confidence {Math.round(sentiment.confidence * 100)}%</span>
        {flagged && <span className="impact-flag">strongly negative</span>}
      </div>

      <div className="sentiment-bar" role="img" aria-label={summary}>
        {SEGMENTS.map((segment, index) =>
          shares[index] > 0 ? (
            <span
              key={segment.key}
              className={`sentiment-seg sentiment-seg-${segment.key}`}
              style={{ flexGrow: shares[index] }}
              title={`${segment.label}: ${Math.round(shares[index] * 100)}%`}
            />
          ) : null
        )}
      </div>

      <ul className="sentiment-legend">
        {SEGMENTS.map((segment, index) => (
          <li key={segment.key}>
            <span className={`sentiment-swatch sentiment-seg-${segment.key}`} aria-hidden="true" />
            {segment.label}
            <b>{Math.round(shares[index] * 100)}%</b>
          </li>
        ))}
      </ul>

      <p className="sentiment-secondary">
        Subjectivity {Math.round(sentiment.subjectivity * 100)}%
        {Number.isFinite(sentiment.emotionalIntensity) &&
          ` · emotional intensity ${Math.round(sentiment.emotionalIntensity * 100)}%`}
      </p>
    </div>
  );
}
