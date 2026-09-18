// Mirrors the *order* of backend/src/config/topics.py's TOPICS dict (not
// its keyword lists - those are richer and change independently server-
// side, and nothing here reads them, so an unused mirrored copy would
// only drift silently, as an earlier version of this file already had).
// That order is what makes a topic's chart position and color stable
// across articles: TopicClassifier only ever returns the topics that
// matched (never the full 22), so without a fixed reference order
// "Education" would land in a different slot - and a different color -
// depending on what else matched that particular article.
const TOPIC_ORDER: string[] = [
  "Education",
  "Community & Social Impact",
  "Employment",
  "Cities & Society",
  "Space",
  "Technology",
  "Scientific Research",
  "Biology",
  "Climate",
  "Nature & Biodiversity",
  "Energy",
  "Sustainability",
  "Food & Agriculture",
  "Arts",
  "Entertainment",
  "History & Heritage",
  "Literature",
  "Inspirational Stories",
  "Medicine",
  "Mental Health",
  "Nutrition",
  "Fitness",
  "Public Health",
];

/** Position in the canonical list - the stable "color slot" for a topic. */
export function topicColorIndex(name: string): number {
  const index = TOPIC_ORDER.indexOf(name);
  return index === -1 ? 0 : index;
}
