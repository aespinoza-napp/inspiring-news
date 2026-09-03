import { Fragment } from "react";
import { PipelineStage } from "@/lib/types";
import { CheckIcon } from "@/components/PhaseStepper";

const STAGES: { id: PipelineStage; label: string; description: string }[] = [
  {
    id: "admission_filter",
    label: "Admission",
    description:
      "Topic relevance, positive-impact score, and duplicate check — the article must clear all three before any claim work begins.",
  },
  {
    id: "claim_selection",
    label: "Selection",
    description:
      "Every sentence is scored for verifiability signals; near-duplicates are dropped and only the top claims by confidence are kept.",
  },
  {
    id: "evidence_retrieval",
    label: "Retrieval",
    description:
      "Cheap candidates are gathered from the web (SearXNG) and the internal archive (Qdrant), then coarsely pre-ranked.",
  },
  {
    id: "evidence_ranking",
    label: "Ranking",
    description:
      "Surviving candidates are re-scored by semantic relevance, recency, and source reliability; only the top few are kept.",
  },
  {
    id: "llm_verification",
    label: "LLM check",
    description:
      "An LLM reads the claim and the ranked evidence, then returns a verdict, a confidence, and which evidence it relied on.",
  },
  {
    id: "confidence_recalibration",
    label: "Recalibration",
    description:
      "The LLM's confidence is blended with an independent evidence-quality score; too little evidence or no citations forces UNVERIFIED.",
  },
  {
    id: "aggregation",
    label: "Done",
    description: "This claim's final verdict, folded into the article's worst-case overall verdict.",
  },
];

/**
 * Per-claim (or article-admission-gate) analog of PhaseStepper: shows how
 * far a single claim got through the 7-stage fact-checking pipeline, with
 * a hover description for every stage and the specific reason inline for
 * whichever stage it stopped at.
 */
export function StageTimeline({
  reachedStage,
  stageNote,
}: {
  reachedStage: PipelineStage;
  stageNote?: string | null;
}) {
  const reachedIndex = STAGES.findIndex((stage) => stage.id === reachedStage);
  const succeeded = reachedStage === "aggregation";
  const stopped = STAGES[reachedIndex];

  return (
    <div className="stage-timeline">
      <ol className="stepper stepper-mini" aria-label="Verification steps for this claim">
        {STAGES.map((stage, index) => {
          const status =
            index < reachedIndex || (index === reachedIndex && succeeded)
              ? "complete"
              : index === reachedIndex
              ? "skipped"
              : "pending";

          return (
            <Fragment key={stage.id}>
              {index > 0 && (
                <li
                  className={`stepper-connector ${index <= reachedIndex ? "is-complete" : ""}`}
                  aria-hidden="true"
                />
              )}
              <li className={`stepper-step is-${status}`} title={stage.description}>
                <span className="stepper-dot" aria-hidden="true">
                  {status === "complete" && <CheckIcon />}
                </span>
                <span className="stepper-label">{stage.label}</span>
              </li>
            </Fragment>
          );
        })}
      </ol>
      {stopped && (
        <p className="stage-timeline-note">
          <strong>{stopped.label}:</strong> {stopped.description}
          {!succeeded && stageNote && <> — {stageNote}</>}
        </p>
      )}
    </div>
  );
}
