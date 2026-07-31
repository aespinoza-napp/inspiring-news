"use client";

import { useState } from "react";
import {
  AnalysisJob,
  ClaimResult,
  PhaseEvent,
  TopicPrediction,
} from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { useAnalysisJob } from "@/lib/useAnalysisJob";

const PHASE_LABELS: Record<string, string> = {
  scraping: "Scraping article",
  scraped: "Article fetched",
  enriching: "Extracting keywords, entities & topics",
  enriched: "Enrichment complete",
  validating: "Checking topic & positivity",
  validated: "Validation complete",
  skipped: "Fact-check skipped",
  selecting_claims: "Selecting claims to verify",
  claims_selected: "Claims selected",
  claim_checked: "Claim verified",
  fact_check_done: "Fact-check complete",
  cache_hit: "Loaded from cache",
  done: "Done",
  failed: "Failed",
};

function phaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase;
}

export default function AnalyzerPage() {
  const [input, setInput] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [urls, setUrls] = useState<string[]>([]);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const parsed = input
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (parsed.length === 0) return;

    setUrls(parsed);
  }

  return (
    <>
      <h1>News Analyzer</h1>
      <p className="subtitle">
        Paste one or more article URLs (one per line) to run them through the
        full pipeline: scraping, enrichment, validation and fact-checking.
        Progress updates every second as each phase completes.
      </p>

      <form onSubmit={handleSubmit}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={
            "https://example.com/article-one\nhttps://example.com/article-two"
          }
        />
        <div className="form-row">
          <button type="submit">Analyze</button>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(event) => setForceRefresh(event.target.checked)}
            />
            Force refresh (skip cache)
          </label>
        </div>
      </form>

      {urls.map((url) => (
        <JobCard key={`${url}:${forceRefresh}`} url={url} forceRefresh={forceRefresh} />
      ))}
    </>
  );
}

function JobCard({ url, forceRefresh }: { url: string; forceRefresh: boolean }) {
  const { job, error } = useAnalysisJob(url, forceRefresh);

  if (error) {
    return (
      <div className="card">
        <span className="card-url">{url}</span>
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="card">
        <span className="card-url">{url}</span>
        <div className="phase-trail">
          <span className="phase-step phase-step-active">Starting...</span>
        </div>
      </div>
    );
  }

  if (job.status === "failed") {
    return (
      <div className="card">
        <span className="card-url">{url}</span>
        <div className="error-banner">{job.error ?? "Analysis failed."}</div>
      </div>
    );
  }

  const partial = summarizeJob(job);
  const isRunning = job.status === "queued" || job.status === "running";

  return (
    <div className="card">
      <h2>
        {partial.title || "(untitled)"}
        {job.result?.cached && <span className="cached-tag">cached</span>}
      </h2>
      <span className="card-url">{url}</span>

      <PhaseTrail events={job.events} isRunning={isRunning} />

      {job.result?.validity && (
        <div className="validity-row">
          <span
            className={`badge ${job.result.validity.isValid ? "badge-true" : "badge-false"}`}
          >
            {job.result.validity.isValid ? "Valid" : "Invalid"}
          </span>
          {job.result.validity.isDuplicate && (
            <span className="badge badge-misleading">Duplicate</span>
          )}
          {!job.result.validity.hasTopic && (
            <span className="badge badge-unverified">No matching topic</span>
          )}
        </div>
      )}

      {partial.keywords.length > 0 && (
        <>
          <div className="section-label">Keywords ({partial.keywords.length})</div>
          <div className="chip-row">
            {partial.keywords.map((keyword) => (
              <span className="chip" key={keyword}>
                {keyword}
              </span>
            ))}
          </div>
        </>
      )}

      {partial.entityCount > 0 && (
        <>
          <div className="section-label">Entities ({partial.entityCount})</div>
          <div className="chip-row">
            {Object.entries(partial.entities).flatMap(([label, values]) =>
              values.map((value) => (
                <span className="chip" key={`${label}-${value}`}>
                  {value} <em>({label})</em>
                </span>
              ))
            )}
          </div>
        </>
      )}

      {partial.topics.length > 0 && (
        <>
          <div className="section-label">Topics ({partial.topics.length})</div>
          {partial.topics.map((topic) => (
            <ScoreBar key={topic.topic} label={topic.topic} value={topic.confidence * 100} />
          ))}
        </>
      )}

      {partial.claims.length > 0 && (
        <>
          <div className="section-label">
            Claims ({partial.claims.length}
            {job.result?.factCheck ? `/${job.result.factCheck.claimsChecked}` : ""})
          </div>
          {partial.claims.map((claim, index) => (
            <div className="claim" key={index}>
              <p className="claim-text">{claim.text}</p>
              <div className="claim-meta">
                <VerdictBadge verdict={claim.verdict} />{" "}
                confidence {Math.round(claim.confidence * 100)}%
                {claim.explanation && <> - {claim.explanation}</>}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function PhaseTrail({ events, isRunning }: { events: PhaseEvent[]; isRunning: boolean }) {
  if (events.length === 0 && !isRunning) return null;

  return (
    <div className="phase-trail">
      {events.map((event, index) => (
        <span className="phase-step" key={index}>
          {phaseLabel(event.phase)}
        </span>
      ))}
      {isRunning && (
        <span className="phase-step phase-step-active">Working...</span>
      )}
    </div>
  );
}

interface PartialResult {
  title: string | null;
  keywords: string[];
  entities: Record<string, string[]>;
  entityCount: number;
  topics: TopicPrediction[];
  claims: ClaimResult[];
}

function summarizeJob(job: AnalysisJob): PartialResult {
  if (job.result) {
    const entities = job.result.entities ?? {};
    return {
      title: job.result.title ?? null,
      keywords: job.result.keywords ?? [],
      entities,
      entityCount: Object.values(entities).reduce((n, v) => n + v.length, 0),
      topics: job.result.topics ?? [],
      claims: job.result.claims ?? [],
    };
  }

  const enrichedEvent = job.events.find((event) => event.phase === "enriched");
  const scrapedEvent = job.events.find((event) => event.phase === "scraped");
  const claimEvents = job.events.filter((event) => event.phase === "claim_checked");

  const entities =
    (enrichedEvent?.data.entities as Record<string, string[]>) ?? {};

  return {
    title:
      (enrichedEvent?.data.title as string) ??
      (scrapedEvent?.data.title as string) ??
      null,
    keywords: (enrichedEvent?.data.keywords as string[]) ?? [],
    entities,
    entityCount: Object.values(entities).reduce((n, v) => n + v.length, 0),
    topics: (enrichedEvent?.data.topics as TopicPrediction[]) ?? [],
    claims: claimEvents.map((event) => ({
      text: event.data.claim as string,
      confidence: event.data.confidence as number,
      verdict: event.data.verdict as ClaimResult["verdict"],
      explanation: event.data.explanation as string | null,
      evidenceCount: 0,
    })),
  };
}
