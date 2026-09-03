import { ClaimResult } from "@/lib/types";

type SourceStatus = "cited" | "considered" | "rejected_ranking" | "rejected_retrieval";

interface SourceBar {
  key: string;
  title: string;
  url: string;
  origin: string;
  score: number | null;
  status: SourceStatus;
}

const LEGEND: { status: SourceStatus; label: string }[] = [
  { status: "cited", label: "Cited by the LLM" },
  { status: "considered", label: "Ranked, not cited" },
  { status: "rejected_ranking", label: "Cut at ranking" },
  { status: "rejected_retrieval", label: "Cut at retrieval funnel" },
];

/**
 * Plots every source a claim's fact-check touched - cited, considered but
 * ignored, and rejected at either funnel stage - as horizontal bars on one
 * ordinal color ramp (one hue, darker = got further through the pipeline).
 * `rejectedSources` also carries "not cited by the LLM" entries (stage
 * llm_verification) that duplicate what `evidence` already reports via its
 * `cited` flag, so those are filtered out here to avoid double-counting.
 */
export function SourcesPlot({ claim }: { claim: ClaimResult }) {
  const bars: SourceBar[] = [
    ...(claim.evidence ?? []).map((item) => ({
      key: item.url,
      title: item.title || item.url,
      url: item.url,
      origin: item.origin,
      score: item.relevanceScore,
      status: (item.cited ? "cited" : "considered") as SourceStatus,
    })),
    ...(claim.rejectedSources ?? [])
      .filter((source) => source.stage !== "llm_verification")
      .map((source) => ({
        key: source.url,
        title: source.title || source.url,
        url: source.url,
        origin: source.origin,
        score: source.score,
        status: (source.stage === "evidence_ranking"
          ? "rejected_ranking"
          : "rejected_retrieval") as SourceStatus,
      })),
  ].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

  if (bars.length === 0) {
    return null;
  }

  return (
    <div className="sources-plot">
      <div className="section-label">Sources considered ({bars.length})</div>
      <div className="source-bar-legend">
        {LEGEND.map(({ status, label }) => (
          <span className="source-bar-legend-item" key={status}>
            <span className={`source-bar-swatch source-bar-fill-${status}`} aria-hidden="true" />
            {label}
          </span>
        ))}
      </div>
      {bars.map((bar) => {
        const percent = Math.max(0, Math.min((bar.score ?? 0) * 100, 100));
        return (
          <div className="source-bar-row" key={bar.key} title={`${bar.title} (${bar.origin})`}>
            <div className="source-bar-label">
              <a className="source-bar-title" href={bar.url} target="_blank" rel="noreferrer">
                {bar.title}
              </a>
              <span className="source-bar-meta">{bar.origin}</span>
            </div>
            <span
              className="source-bar-track"
              role="progressbar"
              aria-label={bar.title}
              aria-valuenow={Math.round(percent)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <span
                className={`source-bar-fill source-bar-fill-${bar.status}`}
                style={{ width: `${percent}%` }}
              />
            </span>
            <span className="source-bar-value">
              {bar.score === null ? "—" : Math.round(percent)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
