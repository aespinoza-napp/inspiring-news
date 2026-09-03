import { PipelineStage } from "@/lib/types";

const LABELS: Record<PipelineStage, string> = {
  admission_filter: "Admission filter",
  claim_selection: "Claim selection",
  evidence_retrieval: "Evidence retrieval",
  evidence_ranking: "Evidence ranking",
  llm_verification: "LLM verification",
  confidence_recalibration: "Confidence recalibration",
  aggregation: "Completed",
};

export function StageBadge({ stage }: { stage: PipelineStage }) {
  const completed = stage === "aggregation";

  return (
    <span className={`badge ${completed ? "badge-true" : "badge-unverified"}`}>
      {completed ? "Completed all 7 stages" : `Stopped at: ${LABELS[stage]}`}
    </span>
  );
}
