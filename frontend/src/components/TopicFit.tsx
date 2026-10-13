import { CSSProperties } from "react";
import { TopicPrediction } from "@/lib/types";

// A topic's confidence is the cosine similarity between the article's
// embedding and the topic's own description (bge-m3; TopicClassifier in
// backend/src/processors/nlp/classifier.py). Those bunch together -
// commonly 0.35-0.55 - so the scale is fitted to the values shown, padded
// and rounded to 0.05, rather than drawn 0-1 where every topic would sit
// in the same narrow strip. It stays the real similarity, though, not
// each topic rescaled against the others: the radar this replaced
// stretched the article's own min-max to the full axis, which made a
// 0.01 difference look like a landslide.
const STEP = 0.05;
const PAD = 0.02;
const MIN_SPAN = 0.15;

// Below this gap the "lead" is noise: two topics this close are a tie.
const TIE_GAP = 0.015;

// Rounded to two decimals so float drift (0.30000000000000004) never
// reaches a label or a position.
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function floorStep(value: number): number {
  return round2(Math.floor(value / STEP) * STEP);
}

function ceilStep(value: number): number {
  return round2(Math.ceil(value / STEP) * STEP);
}

function domain(values: number[], threshold?: number): [number, number] {
  const low = floorStep(Math.min(...values, threshold ?? Infinity) - PAD);
  let high = ceilStep(Math.max(...values) + PAD);

  if (high - low < MIN_SPAN) {
    high = low + MIN_SPAN;
  }

  return [Math.max(0, low), Math.min(1, high)];
}

function ticks([low, high]: [number, number]): number[] {
  const step = (high - low) / STEP > 6 ? STEP * 2 : STEP;
  const out: number[] = [];

  for (let value = low; value <= high + 1e-9; value = round2(value + step)) {
    out.push(value);
  }

  return out;
}

function lead(topics: TopicPrediction[]): string {
  const [first, second] = topics;

  if (!second) {
    return `Only ${first.topic} matched (${first.confidence.toFixed(2)}).`;
  }

  const gap = first.confidence - second.confidence;

  if (gap < TIE_GAP) {
    return `${first.topic} and ${second.topic} are almost tied (${first.confidence.toFixed(2)} and ${second.confidence.toFixed(2)}).`;
  }

  return `Mostly ${first.topic} (${first.confidence.toFixed(2)}), ${gap.toFixed(2)} ahead of ${second.topic}.`;
}

/**
 * The article's top topics as a dot plot on the real similarity scale,
 * best first, with the run's match threshold drawn across every row. The
 * stem runs from the threshold to the dot, so its length is how clearly
 * a topic cleared the bar. The leading topic is in the accent, the rest
 * in gray: the question is "what is this article about", and that is
 * one answer, not five equal series.
 *
 * Each row is a button: picking a topic shows its keywords beside the
 * chart (TopicPanel). The threshold is drawn only once the run's
 * resolved thresholds have arrived, so no default is copied here.
 */
export function TopicFit({
  topics,
  threshold,
  selected,
  onSelect,
}: {
  /** Already the top few, best first. */
  topics: TopicPrediction[];
  threshold?: number;
  selected?: string;
  onSelect?: (topic: string) => void;
}) {
  if (topics.length === 0) {
    return null;
  }

  const scale = domain(topics.map((topic) => topic.confidence), threshold);
  const position = (value: number) =>
    ((value - scale[0]) / (scale[1] - scale[0])) * 100;

  const base = threshold ?? scale[0];

  const plotStyle = {
    "--threshold": `${position(base)}%`,
  } as CSSProperties;

  return (
    <div className="topic-fit">
      <p className="topic-fit-lead">{lead(topics)}</p>

      <div
        className={`topic-fit-plot${threshold != null ? " has-threshold" : ""}`}
        style={plotStyle}
      >
        {threshold != null && (
          <div className="topic-fit-row topic-fit-header" aria-hidden="true">
            <span />
            <span className="topic-fit-track">
              <span className="topic-fit-threshold-label">
                match threshold {threshold.toFixed(2)}
              </span>
            </span>
            <span />
          </div>
        )}

        <ul className="topic-fit-rows">
          {topics.map((topic, index) => {
            const isSelected = topic.topic === selected;
            const x = position(topic.confidence);

            return (
              <li key={topic.topic}>
                <button
                  type="button"
                  className={`topic-fit-row${isSelected ? " is-selected" : ""}`}
                  aria-pressed={onSelect ? isSelected : undefined}
                  aria-label={`${topic.topic}: similarity ${topic.confidence.toFixed(2)}`}
                  disabled={!onSelect}
                  onClick={() => onSelect?.(topic.topic)}
                >
                  <span className="topic-fit-name">{topic.topic}</span>
                  <span className="topic-fit-track">
                    <span
                      className="topic-fit-stem"
                      style={{
                        left: `${Math.min(position(base), x)}%`,
                        width: `${Math.abs(x - position(base))}%`,
                      }}
                    />
                    <span
                      className={`topic-fit-dot${index === 0 ? " is-lead" : ""}`}
                      style={{ left: `${x}%` }}
                      title={`${topic.topic}: ${topic.confidence.toFixed(3)}`}
                    />
                  </span>
                  <span className="topic-fit-value">{topic.confidence.toFixed(2)}</span>
                </button>
              </li>
            );
          })}
        </ul>

        <div className="topic-fit-row topic-fit-axis" aria-hidden="true">
          <span />
          <span className="topic-fit-track">
            {ticks(scale).map((tick) => (
              <span key={tick} className="topic-fit-tick" style={{ left: `${position(tick)}%` }}>
                {tick.toFixed(2)}
              </span>
            ))}
          </span>
          <span />
        </div>
      </div>

      <p className="trace-muted topic-fit-note">
        Similarity between the article and each topic&apos;s description.
        {onSelect ? " Pick a topic to see the keywords behind it." : ""}
      </p>
    </div>
  );
}
