"use client";

import { useState } from "react";
import { AnalysisResult, AnalyzeResponse } from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ScoreBar } from "@/components/ScoreBar";

export default function AnalyzerPage() {
  const [input, setInput] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const urls = input
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (urls.length === 0) return;

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls, forceRefresh }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error ?? `Request failed (${response.status})`);
      }

      setResults((data as AnalyzeResponse).results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1>News Analyzer</h1>
      <p className="subtitle">
        Paste one or more article URLs (one per line) to run them through the
        full pipeline: scraping, enrichment, validation and fact-checking.
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
          <button type="submit" disabled={loading}>
            {loading ? "Analyzing..." : "Analyze"}
          </button>
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

      {error && <div className="error-banner">{error}</div>}

      {results.map((result) => (
        <ResultCard key={result.url} result={result} />
      ))}
    </>
  );
}

function ResultCard({ result }: { result: AnalysisResult }) {
  if (result.error) {
    return (
      <div className="card">
        <span className="card-url">{result.url}</span>
        <div className="error-banner">{result.error}</div>
      </div>
    );
  }

  const entityCount = result.entities
    ? Object.values(result.entities).reduce((n, v) => n + v.length, 0)
    : 0;

  return (
    <div className="card">
      <h2>
        {result.title || "(untitled)"}
        {result.cached && <span className="cached-tag">cached</span>}
      </h2>
      <span className="card-url">{result.url}</span>

      {result.validity && (
        <div className="validity-row">
          <span
            className={`badge ${
              result.validity.isValid ? "badge-true" : "badge-false"
            }`}
          >
            {result.validity.isValid ? "Valid" : "Invalid"}
          </span>
          {result.validity.isDuplicate && (
            <span className="badge badge-misleading">Duplicate</span>
          )}
          {!result.validity.hasTopic && (
            <span className="badge badge-unverified">No matching topic</span>
          )}
        </div>
      )}

      {result.keywords && result.keywords.length > 0 && (
        <>
          <div className="section-label">
            Keywords ({result.keywords.length})
          </div>
          <div className="chip-row">
            {result.keywords.map((keyword) => (
              <span className="chip" key={keyword}>
                {keyword}
              </span>
            ))}
          </div>
        </>
      )}

      {entityCount > 0 && result.entities && (
        <>
          <div className="section-label">Entities ({entityCount})</div>
          <div className="chip-row">
            {Object.entries(result.entities).flatMap(([label, values]) =>
              values.map((value) => (
                <span className="chip" key={`${label}-${value}`}>
                  {value} <em>({label})</em>
                </span>
              ))
            )}
          </div>
        </>
      )}

      {result.topics && result.topics.length > 0 && (
        <>
          <div className="section-label">Topics ({result.topics.length})</div>
          {result.topics.map((topic) => (
            <ScoreBar
              key={topic.topic}
              label={topic.topic}
              value={topic.confidence * 100}
            />
          ))}
        </>
      )}

      {result.claims && result.claims.length > 0 && (
        <>
          <div className="section-label">Claims ({result.claims.length})</div>
          {result.claims.map((claim, index) => (
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
