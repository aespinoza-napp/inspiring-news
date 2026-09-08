"use client";

import { useState } from "react";
import { EnrichmentResult } from "@/lib/types";
import { ScoreBar } from "@/components/ScoreBar";

const QUALITY_METRICS: {
  key: keyof EnrichmentResult["quality"];
  label: string;
}[] = [
  { key: "readability", label: "Readability" },
  { key: "objectivity", label: "Objectivity" },
  { key: "constructiveness", label: "Constructiveness" },
  { key: "inspirationalScore", label: "Inspirational" },
  { key: "hopefulness", label: "Hopefulness" },
  { key: "societalImpact", label: "Societal impact" },
  { key: "novelty", label: "Novelty" },
];

export default function EnrichPage() {
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [result, setResult] = useState<EnrichmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!text.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          title: title.trim() || null,
        }),
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

  return (
    <>
      <h1>Enrichment</h1>
      <p className="subtitle">
        Run only the NLP stage over your own text: keywords, named
        entities, topics, extracted claims, sentiment, quality scores and
        the embedding. It uses the same processors as the article
        analyzer, so this is what the pipeline would derive from this
        text. Nothing is fetched and nothing is stored.
      </p>

      <form onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="enrich-title">
          Title <span className="claims-note">(optional)</span>
        </label>
        <input
          id="enrich-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Headline, if you have one"
        />

        <label className="field-label" htmlFor="enrich-input">
          Text to enrich
        </label>
        <textarea
          id="enrich-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Paste an article body here..."
        />
        <div>
          <button type="submit" disabled={loading}>
            {loading && <span className="spinner" aria-hidden="true" />}
            {loading ? "Enriching…" : "Enrich"}
          </button>
        </div>
      </form>

      {loading && (
        <p className="claims-note">
          Running entity recognition, topic classification, sentiment and
          embeddings — the first run in a fresh backend also loads the
          models, which takes longer.
        </p>
      )}

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="card">
            <div className="section-label">Topics</div>
            {result.topics.length > 0 ? (
              <div className="chip-row">
                {result.topics.map((topic) => (
                  <span className="chip" key={topic.topic}>
                    {topic.topic} · {topic.confidence.toFixed(2)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="claims-note">
                No topic scored above the classifier threshold — the
                article analyzer would reject this text at the admission
                filter.
              </p>
            )}

            <div className="section-label">Keywords</div>
            {result.keywords.length > 0 ? (
              <div className="chip-row">
                {result.keywords.map((keyword) => (
                  <span className="chip" key={keyword}>
                    {keyword}
                  </span>
                ))}
              </div>
            ) : (
              <p className="claims-note">No keywords extracted.</p>
            )}

            <div className="section-label">Entities</div>
            {Object.keys(result.entities).length > 0 ? (
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
            ) : (
              <p className="claims-note">No named entities found.</p>
            )}
          </div>

          <div className="card">
            <div className="section-label">
              Extracted claims ({result.claims.length})
            </div>
            {result.claims.length > 0 ? (
              result.claims.map((claim, index) => (
                <div className="claim" key={index}>
                  <div className="claim-meta">
                    <span className="chip">
                      confidence {claim.confidence.toFixed(2)}
                    </span>
                  </div>
                  <p className="claim-text">{claim.text}</p>
                </div>
              ))
            ) : (
              <p className="claims-note">
                No sentence scored above the claim threshold. Lower
                CLAIM_MIN_CONFIDENCE, or send a claim straight to the
                Claim Check page instead.
              </p>
            )}
          </div>

          <div className="card">
            <div className="section-label">Sentiment</div>
            <div className="claim-meta">
              <span className="chip">{result.sentiment.label}</span>
              <span className="chip">
                confidence {result.sentiment.confidence.toFixed(2)}
              </span>
            </div>
            <ScoreBar label="Positive" value={result.sentiment.positive * 100} />
            <ScoreBar label="Neutral" value={result.sentiment.neutral * 100} />
            <ScoreBar label="Negative" value={result.sentiment.negative * 100} />

            <div className="section-label">Quality</div>
            {QUALITY_METRICS.map(({ key, label }) => (
              <ScoreBar
                key={key}
                label={label}
                value={result.quality[key] * 100}
              />
            ))}
          </div>

          <div className="card">
            <div className="section-label">Embedding</div>
            <p className="metric-summary">
              {result.embedding.dimension} dimensions from{" "}
              <code>{result.embedding.model}</code>. This is the vector the
              duplicate check and the internal evidence lookup compare
              against.
            </p>
            <p className="claims-note">
              [{result.embedding.preview.map((n) => n.toFixed(4)).join(", ")}, …]
            </p>
          </div>
        </>
      )}
    </>
  );
}
