"use client";

import { useState } from "react";
import { EnrichmentResult, ExtractedField, FieldOrigin } from "@/lib/types";
import { ScoreBar } from "@/components/ScoreBar";

const ORIGIN_LABEL: Record<FieldOrigin, string> = {
  supplied: "typed in",
  extracted: "extracted",
  missing: "missing",
};

// Missing is the case this view exists to catch: a missing title
// silently weakens claim selection and the fact checker's subject
// restoration, so it gets the warning colour rather than a neutral tag.
const ORIGIN_CLASS: Record<FieldOrigin, string> = {
  supplied: "trace-tag",
  extracted: "trace-tag trace-tag-ok",
  missing: "trace-tag trace-tag-warn",
};

function OriginTag({ origin }: { origin: FieldOrigin }) {
  return <span className={ORIGIN_CLASS[origin]}>{ORIGIN_LABEL[origin]}</span>;
}

function FieldRow({ label, field }: { label: string; field: ExtractedField }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        {field.value ? (
          <span>{field.value}</span>
        ) : (
          <span className="extraction-missing">not found</span>
        )}{" "}
        <OriginTag origin={field.origin} />
      </dd>
    </>
  );
}

// Only http(s) links are rendered as links: the URL was typed in by
// whoever is using the page, and a javascript: one must stay inert text.
function safeHref(url: string | null): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

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
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [result, setResult] = useState<EnrichmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (!text.trim() && !url.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim() || null,
          title: title.trim() || null,
          url: url.trim() || null,
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
        See what the pipeline extracts from an article. Give it a URL and
        the page is fetched with the same extractor the analyzer uses,
        showing the title, author, date and body it found. Then the NLP
        stage runs: keywords, named entities, topics, claims, sentiment,
        quality and the embedding. You can also paste text instead.
        Nothing is stored.
      </p>

      <form onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="enrich-url">
          Article URL{" "}
          <span className="claims-note">(or paste the text)</span>
        </label>
        <input
          id="enrich-url"
          type="text"
          inputMode="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://..."
        />

        <label className="field-label" htmlFor="enrich-title">
          Title{" "}
          <span className="claims-note">
            (optional)
          </span>
        </label>
        <input
          id="enrich-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Leave empty to use the page's own headline"
        />

        <label className="field-label" htmlFor="enrich-input">
          Text to enrich{" "}
          <span className="claims-note">
            (optional with a URL)
          </span>
        </label>
        <textarea
          id="enrich-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Paste an article body here, or leave empty to use the fetched one..."
        />
        <div>
          <button
            type="submit"
            disabled={loading || (!text.trim() && !url.trim())}
          >
            {loading && <span className="spinner" aria-hidden="true" />}
            {loading
              ? "Enriching…"
              : url.trim()
                ? "Extract & enrich"
                : "Enrich"}
          </button>
        </div>
      </form>

      {loading && (
        <p className="claims-note">
          {url.trim() ? "Fetching the page, then running" : "Running"} entity
          recognition, topic classification, sentiment and embeddings. The
          first run on a fresh backend also loads the models, so it takes
          longer.
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
            <div className="section-label">Extraction</div>

            {result.extraction.error && (
              <div className="error-banner" role="alert">
                {result.extraction.error}
                {result.extraction.body.origin === "supplied" &&
                  " The pasted text was enriched instead."}
              </div>
            )}

            <dl className="extraction-fields">
              {result.extraction.url && (
                <>
                  <dt>URL</dt>
                  <dd>
                    {safeHref(result.extraction.url) ? (
                      <a
                        href={safeHref(result.extraction.url)!}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {result.extraction.url}
                      </a>
                    ) : (
                      result.extraction.url
                    )}
                  </dd>
                </>
              )}
              <FieldRow label="Title" field={result.extraction.title} />
              <FieldRow label="Author" field={result.extraction.author} />
              <FieldRow label="Published" field={result.extraction.publishedAt} />
              <dt>Language</dt>
              <dd>
                {result.language ?? (
                  <span className="extraction-missing">not detected</span>
                )}
              </dd>
              <dt>Body</dt>
              <dd>
                {result.extraction.body.length.toLocaleString()} characters{" "}
                <OriginTag origin={result.extraction.body.origin} />
              </dd>
            </dl>

            {result.extraction.title.origin === "missing" && (
              <p className="claims-note">
                No title was found. The analyzer uses the headline to pick an
                article&apos;s main claims and to put back the subject a claim
                sentence leaves out, so without it claims are checked with
                less context.
              </p>
            )}

            <div className="section-label">Body preview</div>
            <p className="extraction-preview">
              {result.extraction.body.preview}
              {result.extraction.body.length >
                result.extraction.body.preview.length && "…"}
            </p>
          </div>

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
