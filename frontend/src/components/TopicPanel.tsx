"use client";

import { useState } from "react";
import { TopicPrediction } from "@/lib/types";
import { TopicFit } from "@/components/TopicFit";
import { TopicKeywords } from "@/components/TopicKeywords";

const SHOWN = 5;

/**
 * "What is this article about": the top topics on the left, and the
 * keywords behind whichever one is picked on the right - read together as
 * a claim and its evidence. The pick is kept by name, not position, so it
 * survives the list re-sorting while a run is still streaming topics in.
 */
export function TopicPanel({
  topics,
  threshold,
}: {
  topics: TopicPrediction[];
  /** The run's topic_classifier_threshold, once its result has arrived. */
  threshold?: number;
}) {
  const [picked, setPicked] = useState<string | null>(null);

  const top = [...topics]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, SHOWN);

  if (top.length === 0) {
    return null;
  }

  const active = top.find((topic) => topic.topic === picked) ?? top[0];
  const hasKeywords = top.some((topic) => (topic.keywords?.length ?? 0) > 0);

  const count =
    topics.length > SHOWN
      ? `top ${SHOWN} of ${topics.length} matched`
      : `${topics.length} matched`;

  return (
    <div className="topics-row">
      <div className="topics-col">
        <div className="section-label">Top topics ({count})</div>
        <TopicFit
          topics={top}
          threshold={threshold}
          selected={hasKeywords ? active.topic : undefined}
          onSelect={hasKeywords ? setPicked : undefined}
        />
      </div>
      {hasKeywords && (
        <div className="topics-col">
          <div className="section-label">Why “{active.topic}”</div>
          <TopicKeywords topic={active} />
        </div>
      )}
    </div>
  );
}
