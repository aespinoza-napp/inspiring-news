import { TopicPrediction } from "@/lib/types";
import { RadarChart } from "@/components/RadarChart";
import { topicColorIndex } from "@/lib/topicKeywords";

/**
 * The article's top 5 topics (by confidence) as a radar instead of a
 * bar list - each axis is a topic's own display name (e.g. "Education",
 * not the internal id "education" a bug in TopicClassifier used to leak
 * through), weighted by how confidently it matched. Axes are ordered by
 * the same canonical topic order the keyword breakdown next to this
 * chart uses (topicColorIndex), so a topic's spoke/vertex color always
 * matches its dot in that list.
 */
export function TopicRadar({ topics }: { topics: TopicPrediction[] }) {
  const top5 = [...topics]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5)
    .sort((a, b) => topicColorIndex(a.topic) - topicColorIndex(b.topic));

  return (
    <RadarChart
      gradientId="radarFillTopics"
      ariaLabel="Top article topics"
      legendColumns={1}
      axes={top5.map((topic) => ({
        key: topic.topic,
        label: topic.topic,
        value: topic.confidence,
        colorIndex: topicColorIndex(topic.topic),
      }))}
    />
  );
}
