import { CSSProperties } from "react";
import { SentimentScores } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  positive: "var(--true)",
  negative: "var(--false)",
  neutral: "var(--sentiment-neutral)",
};

/**
 * One bipolar meter instead of four separate bars (positive/neutral/
 * negative/subjectivity): a single needle on a negative<->positive track
 * reads faster than four numbers a viewer has to add up themselves.
 *
 * The track itself is a permanent red->amber->green gradient (not a
 * gray bar with a colored fill grown over it) - polarity is a diverging
 * quantity, so the whole scale stays in color, and the headline label is
 * tinted to match instead of defaulting to the page's muted gray text.
 *
 * The thumb position is set once as a `--thumb-pos` custom property on
 * the track, rather than inline `left`/`bottom` in this component: on a
 * laptop-width screen CSS rotates the whole track to vertical (see
 * `.metrics-row .gauge-track` in globals.css) and reads that same
 * property as `bottom` instead of `left` - one value, two axes,
 * depending on viewport, without this component knowing which layout
 * is active.
 */
export function SentimentGauge({ sentiment }: { sentiment: SentimentScores }) {
  const polarity = Math.max(-1, Math.min(sentiment.polarity, 1));
  const thumbPosition = (polarity + 1) / 2; // 0-1 across the track

  const key = sentiment.label?.toLowerCase() ?? "neutral";
  const color = STATUS_COLOR[key] ?? "var(--fg)";

  const label = sentiment.label
    ? sentiment.label.charAt(0).toUpperCase() + sentiment.label.slice(1)
    : "Neutral";

  const trackStyle = {
    "--thumb-pos": `${thumbPosition * 100}%`,
  } as CSSProperties;

  return (
    <div className="gauge">
      <div className="gauge-label" style={{ color }}>
        {label}
        <span className="gauge-meta">
          confidence {Math.round(sentiment.confidence * 100)}%
        </span>
      </div>
      <div className="gauge-body">
        <div
          className="gauge-track"
          role="meter"
          aria-label="Sentiment polarity, negative to positive"
          aria-valuemin={-1}
          aria-valuemax={1}
          aria-valuenow={Math.round(polarity * 100) / 100}
          style={trackStyle}
        >
          <span className="gauge-center-tick" aria-hidden="true" />
          <span className="gauge-thumb" style={{ borderColor: color }} />
        </div>
        <div className="gauge-scale">
          <span>Negative</span>
          <span>Neutral</span>
          <span>Positive</span>
        </div>
      </div>
      <p className="gauge-secondary">
        Subjectivity {Math.round(sentiment.subjectivity * 100)}%
      </p>
    </div>
  );
}
