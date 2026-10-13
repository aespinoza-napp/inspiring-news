import { TopicPrediction } from "@/lib/types";
import { ScoreBar } from "@/components/ScoreBar";

// The least close keyword stays a visible sliver instead of collapsing to
// nothing, which would read as "unrelated" when it belongs to a topic
// that matched.
const MIN_BAR = 0.08;

/**
 * Bars are scaled to this topic's own keywords. The raw similarities of a
 * single word to a whole article are small and bunched together (0.2-0.4),
 * so drawn on a 0-1 axis every bar would look the same; only the order and
 * relative closeness are meaningful, which is why no number is shown.
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
 * The defining keywords of one matched topic (from
 * backend/src/config/topics.py), closest to this article first. A topic
 * matches on whole-article similarity, which says *that* it matched but not
 * *why*; this shows which of the topic's own keywords the article is nearest
 * to. Which topic is chosen in the chart beside it (TopicPanel). A keyword
 * tagged "2×" also appears in the text that many times - many do not, since
 * the lists are English and a Spanish article is scored on meaning.
 */
export function TopicKeywords({ topic }: { topic: TopicPrediction }) {
  const keywords = topic.keywords ?? [];

  if (keywords.length === 0) {
    return (
      <p className="trace-muted topic-keywords-note">
        No keywords were scored for “{topic.topic}”.
      </p>
    );
  }

  const closeness = relativeCloseness(keywords.map((keyword) => keyword.score));

  return (
    <div className="topic-keywords">
      {keywords.map((keyword, index) => (
        <ScoreBar
          key={keyword.keyword}
          label={
            keyword.mentions > 0
              ? `${keyword.keyword} · ${keyword.mentions}×`
              : keyword.keyword
          }
          value={closeness[index] * 100}
          showValue={false}
        />
      ))}

      <p className="trace-muted topic-keywords-note">
        Closest to this article first. “2×” means the word appears in the
        text that many times.
      </p>
    </div>
  );
}
