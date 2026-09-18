import { ScoreBar } from "@/components/ScoreBar";

/**
 * yake (backend/src/processors/nlp/keywords.py) ranks candidates
 * internally but the extractor discards its own raw scores before they
 * reach here - only the order it returned survives extraction. This
 * turns that order back into a displayable strength: the first keyword
 * (yake's strongest pick) reads 100%, the last one 0%, evenly spaced in
 * between - a relative "how central is this term", not a calibrated
 * probability.
 */
function keywordStrength(index: number, total: number): number {
  return total <= 1 ? 100 : 100 * (1 - index / (total - 1));
}

/**
 * The article's own extracted keywords, each with its relative
 * extraction strength - what this specific article is actually about,
 * as opposed to TopicRadar's fixed topic categories.
 */
export function ArticleKeywords({ keywords }: { keywords: string[] }) {
  if (keywords.length === 0) {
    return null;
  }

  return (
    <div className="article-keywords">
      {keywords.map((keyword, index) => (
        <ScoreBar
          key={keyword}
          label={keyword}
          value={keywordStrength(index, keywords.length)}
        />
      ))}
    </div>
  );
}
