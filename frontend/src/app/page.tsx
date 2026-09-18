"use client";

import { useState } from "react";
import {
  AnalysisJob,
  ClaimResult,
  QualityScores,
  SentimentScores,
  TopicPrediction,
} from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";
import { StageTimeline } from "@/components/StageTimeline";
import { SourcesPlot } from "@/components/SourcesPlot";
import { SentimentGauge } from "@/components/SentimentGauge";
import { QualityRadar } from "@/components/QualityRadar";
import { TopicRadar } from "@/components/TopicRadar";
import { TopicKeywordList } from "@/components/TopicKeywordList";
import { PhaseStepper } from "@/components/PhaseStepper";
import { useAnalysisJob } from "@/lib/useAnalysisJob";
import { useBatchAnalysisJobs } from "@/lib/useBatchAnalysisJobs";

export default function AnalyzerPage() {
  const [input, setInput] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
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
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={bulkMode}
              onChange={(event) => setBulkMode(event.target.checked)}
            />
            Bulk mode (one batch submission, with overall progress)
          </label>
        </div>
      </form>

      {bulkMode ? (
        <BulkResults
          key={`${urls.join("\n")}:${forceRefresh}`}
          urls={urls}
          forceRefresh={forceRefresh}
        />
      ) : (
        urls.map((url) => (
          <JobCard key={`${url}:${forceRefresh}`} url={url} forceRefresh={forceRefresh} />
        ))
      )}
    </>
  );
}

function BulkResults({ urls, forceRefresh }: { urls: string[]; forceRefresh: boolean }) {
  const { jobsByUrl, error } = useBatchAnalysisJobs(urls, forceRefresh);

  if (urls.length === 0) return null;

  if (error) {
    return (
      <div className="error-banner" role="alert">
        {error}
      </div>
    );
  }

  const jobs = urls.map((url) => jobsByUrl[url] ?? null);
  const doneCount = jobs.filter((job) => job?.status === "done").length;
  const failedCount = jobs.filter((job) => job?.status === "failed").length;

  return (
    <>
      <div className="batch-summary" role="status">
        <span className="badge badge-true">
          {doneCount} of {urls.length} done
        </span>
        {failedCount > 0 && (
          <span className="badge badge-false">{failedCount} failed</span>
        )}
      </div>

      {urls.map((url, index) => (
        <JobCardView key={`${url}:${index}`} url={url} job={jobs[index]} error={null} />
      ))}
    </>
  );
}

function JobCard({ url, forceRefresh }: { url: string; forceRefresh: boolean }) {
  const { job, error } = useAnalysisJob(url, forceRefresh);

  return <JobCardView url={url} job={job} error={error} />;
}

function JobCardView({
  url,
  job,
  error,
}: {
  url: string;
  job: AnalysisJob | null;
  error: string | null;
}) {
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
          {!!validity.impactReasons?.length && (
            <p className="validity-reasons">
              Impact score {Math.round((validity.impactScore ?? 0) * 100)}/100 — {validity.impactReasons.join(", ")}
            </p>
          )}
          {!validity.isValid && validity.failedStage && (
            <StageTimeline reachedStage={validity.failedStage} stageNote={validity.reasons.join(", ")} />
          )}
        </div>
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
        <div className="topics-row">
          <div className="topics-col">
            <div className="section-label">Top topics ({sortedTopics.length} matched)</div>
            <TopicRadar topics={sortedTopics} />
          </div>
          <div className="topics-col">
            <div className="section-label">Keywords for {sortedTopics[0].topic}</div>
            <TopicKeywordList
              topic={sortedTopics[0].topic}
              articleKeywords={partial.keywords}
            />
          </div>
        </div>
      )}

      {(partial.sentiment || partial.quality) && (
        <div className="metrics-row">
          {partial.sentiment && (
            <div className="metrics-col">
              <div className="section-label">Sentiment</div>
              <SentimentGauge sentiment={partial.sentiment} />
            </div>
          )}
          {partial.quality && (
            <div className="metrics-col metrics-col-wide">
              <div className="section-label">Impact &amp; quality</div>
              <QualityRadar quality={partial.quality} />
            </div>
          )}
        </div>
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
          {job.result?.factCheck?.belowAnchorFloor && (
            <p className="claims-note">
              Fewer load-bearing claims were found than this run asks for, so
              the verdict rests on less than a full set of anchors.
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
              {claim.reachedStage && (
                <StageTimeline reachedStage={claim.reachedStage} stageNote={claim.stageNote} />
              )}
              {claim.rawVerdict && claim.rawVerdict !== claim.verdict && (
                <p className="claims-note">
                  The LLM originally said {claim.rawVerdict} (
                  {Math.round((claim.rawConfidence ?? 0) * 100)}% confidence) — recalibration
                  changed the final verdict to {claim.verdict ?? "UNVERIFIED"}.
                </p>
              )}
              <ClaimComparison claim={claim} />
              <SourcesPlot claim={claim} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function ClaimComparison({ claim }: { claim: ClaimResult }) {
  const agreements = claim.agreements ?? [];
  const discrepancies = claim.discrepancies ?? [];

  if (agreements.length === 0 && discrepancies.length === 0) {
    return null;
  }

  return (
    <div className="comparison-block">
      {agreements.length > 0 && (
        <div className="comparison-agreements">
          <p className="comparison-group-title">
            Confirmed by {claim.independentDomains ?? agreements.length} source
            {(claim.independentDomains ?? agreements.length) === 1 ? "" : "s"}
          </p>
          <ul className="comparison-list">
            {agreements.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {discrepancies.length > 0 && (
        <div className="comparison-discrepancies">
          <p className="comparison-group-title">Where sources differ</p>
          <ul className="comparison-list">
            {discrepancies.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
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
  sentiment: SentimentScores | null;
  quality: QualityScores | null;
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
      sentiment: job.result.sentiment ?? null,
      quality: job.result.quality ?? null,
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
    sentiment: (enrichedEvent?.data.sentiment as SentimentScores) ?? null,
    quality: (enrichedEvent?.data.quality as QualityScores) ?? null,
    claims: claimEvents.map((event) => ({
      text: event.data.claim as string,
      confidence: event.data.confidence as number,
      verdict: event.data.verdict as ClaimResult["verdict"],
      explanation: event.data.explanation as string | null,
      evidenceCount: 0,
    })),
  };
}
