"use client";

import { useState } from "react";
import { ClaimVerification } from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ScoreBar } from "@/components/ScoreBar";

export default function ClaimPage() {
  const [claim, setClaim] = useState("");
  const [result, setResult] = useState<ClaimVerification | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!claim.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/verify-claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.error ?? data?.detail ?? `Request failed (${response.status})`
        );
      }

      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  // The verdict was recalibrated away from what the LLM answered - either
  // no evidence was retrieved at all, or it gave a definitive answer while
  // citing nothing. Worth showing plainly rather than quietly presenting
  // the downgraded verdict as if the model had said it.
  const downgraded =
    result?.rawVerdict != null && result.rawVerdict !== result.verdict;

  return (
    <>
      <h1>Claim Check</h1>
      <p className="subtitle">
        Verify a single claim on its own. This runs the same verification
        stage the article analyzer uses — evidence retrieval, ranking, an
        LLM judgement, then confidence recalibration — so the verdict
        matches what a full article run would give the same claim. The
        article-level filters (topic, positivity, duplicates) do not
        apply here.
      </p>

      <form onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="claim-input">
          Claim to verify
        </label>
        <textarea
          id="claim-input"
          value={claim}
          onChange={(event) => setClaim(event.target.value)}
          placeholder="e.g. A clinical trial reported a 94% remission rate for a new leukemia treatment."
          rows={3}
        />
        <div>
          <button type="submit" disabled={loading}>
            {loading && <span className="spinner" aria-hidden="true" />}
            {loading ? "Checking…" : "Check claim"}
          </button>
        </div>
      </form>

      {loading && (
        <p className="claims-note">
          Searching for evidence and asking the model — this takes a few
          seconds, and needs SearXNG and the LLM endpoint running.
        </p>
      )}

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="card">
          <div className="claim-meta">
            <VerdictBadge verdict={result.verdict} />
            <span className="chip">
              {result.evidenceCount} evidence item
              {result.evidenceCount === 1 ? "" : "s"}
            </span>
            <span className="chip">stage: {result.reachedStage}</span>
          </div>

          <p className="claim-text">{result.claim}</p>

          <ScoreBar label="Confidence" value={result.confidence * 100} />

          <p className="metric-summary">{result.explanation}</p>

          {downgraded && (
            <p className="claims-note">
              The model answered <strong>{result.rawVerdict}</strong> at{" "}
              {Math.round((result.rawConfidence ?? 0) * 100)}% confidence, but
              the verdict was downgraded: {result.stageNote}
            </p>
          )}

          {Object.keys(result.entities).length > 0 && (
            <div className="entity-groups">
              {Object.entries(result.entities).map(([group, values]) => (
                <div className="entity-group" key={group}>
                  <span className="entity-group-tag">{group}</span>
                  <div className="chip-row">
                    {values.map((value) => (
                      <span className="chip" key={value}>
                        {value}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {result.evidence.length > 0 ? (
            <>
              <div className="section-label">Evidence</div>
              <ul className="metric-issues">
                {result.evidence.map((item) => (
                  <li key={item.url}>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title || item.url}
                    </a>{" "}
                    <span className="chip">{item.origin}</span>
                    {item.cited && <span className="chip">cited</span>}
                    {item.relevanceScore != null && (
                      <span className="chip">
                        {item.relevanceScore.toFixed(2)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="claims-note">
              No evidence was retrieved, so the verdict is forced to
              Unverified regardless of what the model answered.
            </p>
          )}

          {result.rejectedSources.length > 0 && (
            <>
              <div className="section-label">
                Considered but not used ({result.rejectedSources.length})
              </div>
              <ul className="metric-issues">
                {result.rejectedSources.map((source, index) => (
                  <li key={`${source.url}-${index}`}>
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title || source.url}
                    </a>{" "}
                    — {source.reason}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </>
  );
}
