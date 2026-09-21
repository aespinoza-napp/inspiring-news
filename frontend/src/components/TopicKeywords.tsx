"use client";

import { useState } from "react";
import { TopicPrediction } from "@/lib/types";
import { ScoreBar } from "@/components/ScoreBar";
import { seriesColor } from "@/lib/palette";
import { topicColorIndex } from "@/lib/topicKeywords";

// Same floor as TopicRadar: the least close keyword stays a visible
// sliver instead of collapsing to nothing, which would read as "unrelated"
// when it belongs to a topic that matched.
const MIN_BAR = 0.08;

/**
 * Bars are scaled to this topic's own keywords. The raw similarities of a
 * single word to a whole article are small and bunched together (0.2-0.4),
 * so drawn on a 0-1 axis every bar would look the same; only the order and
 * relative closeness are meaningful.
 */
function relativeCloseness(scores: number[]): number[] {
  const max = Math.max(...scores);
  const min = Math.min(...scores);

  if (max === min) {
    return scores.map(() => 1);
  }

  return scores.map(
    (score) => MIN_BAR + (1 - MIN_BAR) * ((score - min) / (max - min))
  );
}

/**
 * The defining keywords of the article's matched topics (from
 * backend/src/config/topics.py), closest to this article first. A topic
 * matches on whole-article similarity, which says *that* it matched but not
 * *why*; this shows which of the topic's own keywords the article is nearest
 * to. A keyword tagged "2×" also appears in the text that many times - many
 * do not, since the lists are English and a Spanish article is scored on
 * meaning.
 */
export function TopicKeywords({ topics }: { topics: TopicPrediction[] }) {
  const top = [...topics]
    .filter((topic) => (topic.keywords?.length ?? 0) > 0)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);

  const [selected, setSelected] = useState(0);

  if (top.length === 0) {
    return null;
  }

  const active = top[Math.min(selected, top.length - 1)];
  const keywords = active.keywords ?? [];
  const closeness = relativeCloseness(keywords.map((keyword) => keyword.score));
  const color = seriesColor(topicColorIndex(active.topic));

  return (
    <div className="topic-keywords">
      <div className="topic-keywords-tabs" role="tablist" aria-label="Topic">
        {top.map((topic, index) => (
          <button
            key={topic.topic}
            type="button"
            role="tab"
            aria-selected={topic === active}
            className={`topic-keywords-tab${topic === active ? " is-active" : ""}`}
            onClick={() => setSelected(index)}
          >
            <span
              className="topic-keywords-dot"
              style={{ background: seriesColor(topicColorIndex(topic.topic)) }}
              aria-hidden="true"
            />
            {topic.topic}
          </button>
        ))}
      </div>

      {keywords.map((keyword, index) => (
        <ScoreBar
          key={keyword.keyword}
          label={
            keyword.mentions > 0
              ? `${keyword.keyword} · ${keyword.mentions}×`
              : keyword.keyword
          }
          value={closeness[index] * 100}
          color={color}
          showValue={false}
        />
      ))}

      <p className="trace-muted topic-keywords-note">
        Keywords of “{active.topic}”, closest to this article first.{" "}
        “2×” means the word appears in the text that many times.
      </p>
    </div>
  );
}
