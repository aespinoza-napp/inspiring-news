export interface TopicDefinition {
  name: string;
  keywords: string[];
}

// Mirrors backend/src/config/topics.py's TOPICS dict, in the same
// declared order. That order is what makes a topic's chart position and
// color stable across articles: TopicClassifier only ever returns the
// topics that matched (never the full 22), so without a fixed reference
// order "Education" would land in a different slot - and a different
// color - depending on what else matched that particular article.
export const TOPIC_DEFINITIONS: TopicDefinition[] = [
  { name: "Education", keywords: ["education", "school", "university", "student", "teacher", "learning", "curriculum"] },
  { name: "Community & Social Impact", keywords: ["community", "volunteer", "charity", "social impact", "nonprofit", "activism"] },
  { name: "Employment", keywords: ["employment", "career", "jobs", "workforce", "entrepreneurship", "skills"] },
  { name: "Cities & Society", keywords: ["city", "urban", "housing", "mobility", "community", "transport"] },
  { name: "Space", keywords: ["space", "NASA", "ESA", "SpaceX", "Mars", "Moon"] },
  { name: "Technology", keywords: ["technology", "software", "robotics", "cybersecurity", "cloud", "automation"] },
  { name: "Scientific Research", keywords: ["research", "discovery", "science", "innovation", "breakthrough"] },
  { name: "Biology", keywords: ["biology", "DNA", "genetics", "microbiology", "evolution"] },
  { name: "Climate", keywords: ["climate change", "global warming", "carbon", "net zero", "emissions"] },
  { name: "Nature & Biodiversity", keywords: ["wildlife", "biodiversity", "ecosystem", "species", "conservation"] },
  { name: "Energy", keywords: ["renewable energy", "solar", "wind", "battery", "hydrogen"] },
  { name: "Sustainability", keywords: ["sustainability", "circular economy", "recycling", "green technology", "eco-friendly"] },
  { name: "Food & Agriculture", keywords: ["agriculture", "food production", "organic food", "marine", "ocean"] },
  { name: "Arts", keywords: ["art", "museum", "architecture", "dance", "theatre"] },
  { name: "Entertainment", keywords: ["movie", "film", "music", "concert", "festival"] },
  { name: "History & Heritage", keywords: ["history", "archaeology", "heritage", "civilization"] },
  { name: "Literature", keywords: ["book", "author", "novel", "literature"] },
  { name: "Inspirational Stories", keywords: ["success", "kindness", "volunteer", "achievement", "role model"] },
  { name: "Medicine", keywords: ["medicine", "healthcare", "vaccine", "therapy", "clinical trial"] },
  { name: "Mental Health", keywords: ["mental health", "psychology", "wellbeing", "mindfulness", "depression"] },
  { name: "Nutrition", keywords: ["nutrition", "healthy eating", "diet", "healthy recipes"] },
  { name: "Fitness", keywords: ["fitness", "exercise", "gym", "running", "training"] },
  { name: "Public Health", keywords: ["public health", "prevention", "epidemiology", "health policy", "WHO"] },
];

/** Position in the canonical list - the stable "color slot" for a topic. */
export function topicColorIndex(name: string): number {
  const index = TOPIC_DEFINITIONS.findIndex((topic) => topic.name === name);
  return index === -1 ? 0 : index;
}

export function topicKeywords(name: string): string[] {
  return TOPIC_DEFINITIONS.find((topic) => topic.name === name)?.keywords ?? [];
}
