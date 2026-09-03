import { Fragment } from "react";
import { JobStatus, PhaseEvent } from "@/lib/types";

type StageStatus = "pending" | "active" | "complete" | "skipped" | "error";

interface Stage {
  id: string;
  label: string;
  status: StageStatus;
  note?: string;
}

// One-line description of what's happening right now, keyed by the most
// recent phase event seen. Distinct from the stepper's per-stage labels,
// which describe the five coarse-grained stages, not every fine-grained
// backend phase.
const CURRENT_PHASE_LABELS: Record<string, string> = {
  initializing: "Warming up (loading local AI models, first run only)…",
  initialized: "Models ready",
  scraping: "Fetching the article…",
  scraped: "Article fetched",
  enriching: "Extracting keywords, entities & topics…",
  enriched: "Enrichment complete",
  validating: "Checking topic & positivity…",
  validated: "Validation complete",
  skipped: "Fact-check skipped — article did not pass validation",
  selecting_claims: "Selecting claims to verify…",
  claims_selected: "Claims selected",
  claim_checked: "Checking claims…",
  fact_check_done: "Fact-check complete",
};

/**
 * Renders the job's phase events (see useAnalysisJob) as a five-stage
 * progress timeline: Fetch -> Enrich -> Validate -> Fact-check -> Done.
 * Several fine-grained backend phases collapse into each stage (e.g.
 * "scraping"/"scraped" both belong to "Fetch"); the stage is "active"
 * while its start phase has fired but not yet its end phase.
 */
export function PhaseStepper({
  events,
  status,
}: {
  events: PhaseEvent[];
  status: JobStatus;
}) {
  const phases = new Set(events.map((event) => event.phase));
  const has = (phase: string) => phases.has(phase);
  const isQueuedOrRunning = status === "queued" || status === "running";
  const isFailed = status === "failed";
  const isDone = status === "done";
  const isSkipped = has("skipped");

  const claimsSelectedEvent = events.find(
    (event) => event.phase === "claims_selected"
  );
  const claimsSelectedCount =
    (claimsSelectedEvent?.data.count as number | undefined) ?? null;
  const claimsCheckedCount = events.filter(
    (event) => event.phase === "claim_checked"
  ).length;

  const stages: Stage[] = [
    {
      id: "scrape",
      label: "Fetch",
      status:
        isFailed && !has("scraped")
          ? "error"
          : has("scraped")
          ? "complete"
          : has("scraping") || isQueuedOrRunning
          ? "active"
          : "pending",
    },
    {
      id: "enrich",
      label: "Enrich",
      status: has("enriched")
        ? "complete"
        : has("enriching")
        ? "active"
        : "pending",
    },
    {
      id: "validate",
      label: "Validate",
      status:
        has("validated") || isSkipped
          ? "complete"
          : has("validating")
          ? "active"
          : "pending",
    },
    {
      id: "factcheck",
      label: "Fact-check",
      status: isSkipped
        ? "skipped"
        : has("fact_check_done")
        ? "complete"
        : has("selecting_claims") ||
          has("claims_selected") ||
          has("claim_checked")
        ? "active"
        : "pending",
      note:
        !isSkipped && claimsSelectedCount
          ? `${claimsCheckedCount}/${claimsSelectedCount} claims`
          : undefined,
    },
    {
      id: "done",
      label: "Done",
      status: isDone ? "complete" : isFailed ? "error" : "pending",
    },
  ];

  const lastEvent = events[events.length - 1];
  const statusLine = isFailed
    ? "Failed"
    : isDone
    ? "Complete"
    : lastEvent
    ? CURRENT_PHASE_LABELS[lastEvent.phase] ?? lastEvent.phase
    : "Starting…";

  return (
    <div className="stepper-wrap">
      <ol className="stepper" aria-label="Analysis progress">
        {stages.map((stage, index) => (
          <Fragment key={stage.id}>
            {index > 0 && (
              <li
                className={`stepper-connector ${
                  stages[index - 1].status === "complete" ? "is-complete" : ""
                }`}
                aria-hidden="true"
              />
            )}
            <li className={`stepper-step is-${stage.status}`}>
              <span className="stepper-dot" aria-hidden="true">
                {stage.status === "complete" && <CheckIcon />}
                {stage.status === "error" && "!"}
              </span>
              <span className="stepper-label">
                {stage.label}
                {stage.status === "skipped" && " · skipped"}
              </span>
              {stage.note && <span className="stepper-note">{stage.note}</span>}
            </li>
          </Fragment>
        ))}
      </ol>
      {(isQueuedOrRunning || isFailed) && (
        <div className="stepper-status" role="status">
          {isQueuedOrRunning && <span className="spinner" aria-hidden="true" />}
          <span>{statusLine}</span>
        </div>
      )}
    </div>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="9" height="9" aria-hidden="true">
      <path
        d="M3 8.5l3 3 7-7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
