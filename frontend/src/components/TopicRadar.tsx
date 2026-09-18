import { TopicPrediction } from "@/lib/types";
import { RadarChart } from "@/components/RadarChart";
import { topicColorIndex } from "@/lib/topicKeywords";

// Topic confidence is a raw cosine similarity between the article's
// embedding and each topic's own description embedding
// (TopicClassifier.process, backend/src/processors/nlp/classifier.py).
// Those cluster tightly - commonly 0.35-0.55 - even when one topic is
// clearly the article's real subject, so plotting them as-is on the
// chart's 0-1 axis draws an almost-regular polygon no matter how
// distinct the actual match is: every axis looks about the same length.
//
// Rescaled here to *this article's own* min/max among its matched
// topics, so the shape shows relative dominance - which of these
// specific topics this article leans toward - instead of the raw
// similarity band. MIN_SPOKE keeps the least relevant of the topics
// shown visible as a small spoke rather than collapsing to the center,
// which would misread as "didn't match" when it did clear the
// classifier's threshold.
const MIN_SPOKE = 0.15;

function relativeRelevance(confidences: number[]): number[] {
  const max = Math.max(...confidences);
  const min = Math.min(...confidences);

  if (max === min) {
    return confidences.map(() => 1);
  }

  return confidences.map(
    (value) => MIN_SPOKE + (1 - MIN_SPOKE) * ((value - min) / (max - min))
  );
}

/**
 * The article's top 5 topics (by confidence) as a radar instead of a
 * bar list - each axis is a topic's own display name (e.g. "Education",
 * not the internal id "education" a bug in TopicClassifier used to leak
 * through), sized by its relevance *relative to the other matched
 * topics*, not its raw confidence - see relativeRelevance() above.
 * Axes are ordered by the same canonical topic order the keyword
 * breakdown next to this chart used to use (topicColorIndex), so a
 * topic's spoke/vertex color stays stable across articles.
 */
export function TopicRadar({ topics }: { topics: TopicPrediction[] }) {
  const top5 = [...topics]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);

  const relevance = relativeRelevance(top5.map((topic) => topic.confidence));

  const ordered = top5
    .map((topic, index) => ({ topic, relevance: relevance[index] }))
    .sort((a, b) => topicColorIndex(a.topic.topic) - topicColorIndex(b.topic.topic));

  return (
    <RadarChart
      gradientId="radarFillTopics"
      ariaLabel="Top article topics, by relevance relative to each other"
      legendColumns={1}
      axes={ordered.map(({ topic, relevance }) => ({
        key: topic.topic,
        label: topic.topic,
        value: relevance,
        colorIndex: topicColorIndex(topic.topic),
      }))}
    />
  );
}
