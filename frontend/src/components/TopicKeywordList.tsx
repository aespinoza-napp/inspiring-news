import { ScoreBar } from "@/components/ScoreBar";
import { seriesColor } from "@/lib/palette";
import { topicColorIndex, topicKeywords } from "@/lib/topicKeywords";

/**
 * How strongly each of the topic's own defining keywords (from
 * src/config/topics.py) actually shows up among the article's yake
 * keywords - the classifier matches on whole-article embedding
 * similarity, which says *that* a topic matched but not *why*. Matching
 * is substring-based both ways (yake returns short phrases, topic
 * keywords are sometimes multi-word) and weighted by the yake keyword's
 * own rank, since yake discards its raw scores and only the order
 * survives past extraction (see keywords.py).
 */
function representation(keyword: string, articleKeywords: string[]): number {
  const needle = keyword.toLowerCase();
  let best = 0;

  articleKeywords.forEach((found, rank) => {
    const hay = found.toLowerCase();
    if (hay.includes(needle) || needle.includes(hay)) {
      const strength = 1 - rank / articleKeywords.length;
      best = Math.max(best, strength);
    }
  });

  return best;
}

export function TopicKeywordList({
  topic,
  articleKeywords,
}: {
  topic: string;
  articleKeywords: string[];
}) {
  const keywords = topicKeywords(topic);
  if (keywords.length === 0) {
    return null;
  }

  const color = seriesColor(topicColorIndex(topic));

  return (
    <div className="topic-keywords">
      {keywords.map((keyword) => (
        <ScoreBar
          key={keyword}
          label={keyword}
          value={representation(keyword, articleKeywords) * 100}
          color={color}
          swatch
        />
      ))}
    </div>
  );
}
