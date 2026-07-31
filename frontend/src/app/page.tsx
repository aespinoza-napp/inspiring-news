"use client";

import { useState } from "react";
import {
  AnalysisJob,
  ClaimResult,
  TopicPrediction,
} from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { PhaseStepper } from "@/components/PhaseStepper";
import { useAnalysisJob } from "@/lib/useAnalysisJob";

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
        <label className="field-label" htmlFor="urls-input">
          Article URLs
        </label>
        <textarea
          id="urls-input"
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
        <div className="error-banner" role="alert">
          {error}
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="card">
        <span className="card-url">{url}</span>
        <div className="stepper-status" role="status">
          <span className="spinner" aria-hidden="true" />
          <span>Starting…</span>
        </div>
      </div>
    );
  }

  const partial = summarizeJob(job);
  const isFailed = job.status === "failed";
  const isRunning = job.status === "queued" || job.status === "running";
  const cached = job.result?.cached ?? false;
  const sortedTopics = [...partial.topics].sort(
    (a, b) => b.confidence - a.confidence
  );
  const validity = job.result?.validity;
  const claimsChecked = job.result?.factCheck?.claimsChecked ?? 0;
  const showUncheckedNote =
    !!validity && !validity.isValid && claimsChecked === 0 && partial.claims.length > 0;

  return (
    <div className="card">
      <h2>
        {partial.title ||
          (isFailed ? "Analysis failed" : isRunning ? "Analyzing…" : "(untitled)")}
        {cached && <span className="cached-tag">Cached</span>}
      </h2>
      <span className="card-url">{url}</span>

      {cached ? (
        <div className="stepper-status stepper-status-cached">
          Loaded instantly from cache
        </div>
      ) : (
        <PhaseStepper events={job.events} status={job.status} />
      )}

      {isFailed && (
        <div className="error-banner" role="alert">
          {job.error ?? "Analysis failed."}
        </div>
      )}

      {validity && (
        <div className="validity-block">
          <div className="validity-row">
            <span className={`badge ${validity.isValid ? "badge-true" : "badge-false"}`}>
              {validity.isValid ? "Valid" : "Invalid"}
            </span>
            {validity.isDuplicate && (
              <span className="badge badge-misleading">Duplicate</span>
            )}
            {!validity.hasTopic && (
              <span className="badge badge-unverified">No matching topic</span>
            )}
          </div>
          {!validity.isValid && validity.reasons.length > 0 && (
            <p className="validity-reasons">Why: {validity.reasons.join(", ")}</p>
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
          <div className="entity-groups">
            {Object.entries(partial.entities).map(([label, values]) => (
              <div className="entity-group" key={label}>
                <span className="entity-group-tag">{label}</span>
                <div className="chip-row">
                  {values.map((value) => (
                    <span className="chip" key={`${label}-${value}`}>
                      {value}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {sortedTopics.length > 0 && (
        <>
          <div className="section-label">Topics ({sortedTopics.length})</div>
          {sortedTopics.map((topic) => (
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
          {showUncheckedNote && (
            <p className="claims-note">
              This article didn&apos;t pass validation, so these claims were
              not fact-checked.
            </p>
          )}
          {partial.claims.map((claim, index) => (
            <div
              className={`claim claim-verdict-${(claim.verdict ?? "none").toLowerCase()}`}
              key={`${claim.text}-${index}`}
            >
              <p className="claim-text">{claim.text}</p>
              <div className="claim-meta">
                <VerdictBadge verdict={claim.verdict} />
                <span>confidence {Math.round(claim.confidence * 100)}%</span>
                {claim.explanation && <span>{claim.explanation}</span>}
              </div>
            </div>
          ))}
        </>
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
