"use client";

import { useState } from "react";
import { ClaimResult, EvidenceStance } from "@/lib/types";

type SourceStatus = "cited" | "considered" | "rejected_ranking" | "rejected_retrieval";

interface SourceBar {
  key: string;
  title: string;
  url: string;
  origin: string;
  score: number | null;
  status: SourceStatus;
  domain?: string | null;
  engines?: string[];
  semantic?: number | null;
  recency?: number | null;
  reliability?: number | null;
  stance?: EvidenceStance | null;
  quote?: string | null;
  reason?: string;
}

const LEGEND: { status: SourceStatus; label: string }[] = [
  { status: "cited", label: "Cited by the LLM" },
  { status: "considered", label: "Ranked, not cited" },
  { status: "rejected_ranking", label: "Cut at ranking" },
  { status: "rejected_retrieval", label: "Cut at retrieval funnel" },
];

const STANCE_LABELS: Record<EvidenceStance, string> = {
  supports: "Supports",
  contradicts: "Contradicts",
  unrelated: "Unrelated",
};

/**
 * Plots every source a claim's fact-check touched - cited, considered but
 * ignored, and rejected at either funnel stage - as horizontal bars on one
 * ordinal color ramp (one hue, darker = got further through the pipeline).
 * `rejectedSources` also carries "not cited by the LLM" entries (stage
 * llm_verification) that duplicate what `evidence` already reports via its
 * `cited` flag, so those are filtered out here to avoid double-counting.
 *
 * Each row expands to show *why* it sits where it does: the three factors
 * the ranker combined into the score, what this source says about the
 * claim, and the span it was judged on. The composite score alone can say
 * that one source outranked another but never why - and "why" is the only
 * question a reader actually has about a ranking.
 */
export function SourcesPlot({ claim }: { claim: ClaimResult }) {
  const [openKey, setOpenKey] = useState<string | null>(null);

  const bars: SourceBar[] = [
    ...(claim.evidence ?? []).map((item) => ({
      key: item.url,
      title: item.title || item.url,
      url: item.url,
      origin: item.origin,
      score: item.relevanceScore,
      status: (item.cited ? "cited" : "considered") as SourceStatus,
      domain: item.domain,
      engines: item.engines,
      semantic: item.semanticScore,
      recency: item.recencyScore,
      reliability: item.reliabilityScore,
      stance: item.stance,
      quote: item.quote,
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
        reason: source.reason,
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
        const open = openKey === bar.key;
        const hasDetail =
          bar.semantic != null || bar.quote != null || !!bar.reason || !!bar.stance;

        return (
          <div className="source-row-group" key={bar.key}>
            <div className="source-bar-row">
              <div className="source-bar-label">
                <a className="source-bar-title" href={bar.url} target="_blank" rel="noreferrer">
                  {bar.title}
                </a>
                <span className="source-bar-meta">
                  {bar.domain || bar.origin}
                  {bar.stance && (
                    <span className={`stance-chip stance-${bar.stance}`}>
                      {STANCE_LABELS[bar.stance]}
                    </span>
                  )}
                </span>
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
              {hasDetail && (
                <button
                  type="button"
                  className="source-why"
                  aria-expanded={open}
                  onClick={() => setOpenKey(open ? null : bar.key)}
                >
                  {open ? "Hide" : "Why?"}
                </button>
              )}
            </div>

            {open && (
              <div className="source-detail">
                {bar.semantic != null && (
                  <dl className="source-factors">
                    <Factor label="Relevance" value={bar.semantic} weight="60%" />
                    <Factor label="Recency" value={bar.recency} weight="25%" />
                    <Factor label="Reliability" value={bar.reliability} weight="15%" />
                  </dl>
                )}
                {bar.quote && <blockquote className="source-quote">{bar.quote}</blockquote>}
                {bar.stance && !bar.quote && (
                  <p className="source-detail-note">
                    No verbatim span could be confirmed in this source, so none is shown.
                  </p>
                )}
                {bar.reason && <p className="source-detail-note">{bar.reason}</p>}
                {!!bar.engines?.length && (
                  <p className="source-detail-note">
                    Found by {bar.engines.join(", ")}
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Factor({
  label,
  value,
  weight,
}: {
  label: string;
  value: number | null | undefined;
  weight: string;
}) {
  return (
    <div className="source-factor">
      <dt>
        {label} <span className="source-factor-weight">×{weight}</span>
      </dt>
      <dd>
        <span className="source-factor-track">
          <span
            className="source-factor-fill"
            style={{ width: `${Math.max(0, Math.min((value ?? 0) * 100, 100))}%` }}
          />
        </span>
        <span className="source-factor-value">
          {value == null ? "—" : Math.round(value * 100)}
        </span>
      </dd>
    </div>
  );
}
