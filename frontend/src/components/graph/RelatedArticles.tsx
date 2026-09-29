"use client";

import { useEffect, useState } from "react";
import { VerdictBadge } from "@/components/VerdictBadge";
import { safeHref, truncate } from "@/lib/graphStyle";
import { GraphArticle, RelatedArticle, RelatedArticles as Related, Verdict } from "@/lib/types";

const KIND_LABELS: Record<RelatedArticle["shared"][number]["kind"], string> = {
  claim: "Same claim",
  evidence: "Same evidence",
  entity: "Same entity",
  topic: "Same topic",
};

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, "");
}

/**
 * The graph's read use-case: pick an article, see which others it is
 * connected to and exactly through what. The weights are the backend's
 * (graph_reader.py RELATED_ARTICLES) and are shown next to each shared
 * thing, so a score is never an unexplained number.
 */
export function RelatedArticles({
  articles,
  url,
  onPick,
  onShowGraph,
}: {
  articles: GraphArticle[];
  url: string | null;
  onPick: (url: string) => void;
  onShowGraph: (url: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState<GraphArticle[]>(articles);
  const [related, setRelated] = useState<Related | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setMatches(articles), [articles]);

  // Server-side search, debounced: the list on the page holds at most the
  // 200 most recent articles, the graph may hold more.
  useEffect(() => {
    if (!search.trim()) {
      setMatches(articles);
      return;
    }

    let cancelled = false;

    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/graph/articles?limit=50&search=${encodeURIComponent(search.trim())}`
        );
        const data = await response.json();
        if (!cancelled && response.ok) setMatches(data.articles);
      } catch {
        // Keep the previous matches; the related view shows real errors.
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [search, articles]);

  useEffect(() => {
    if (!url) {
      setRelated(null);
      return;
    }

    let cancelled = false;

    setLoading(true);
    setError(null);

    fetch(`/api/graph/related?limit=15&url=${encodeURIComponent(url)}`)
      .then(async (response) => {
        const data = await response.json();
        if (cancelled) return;
        if (!response.ok) throw new Error(data.detail ?? data.error ?? `Failed (${response.status})`);
        setRelated(data as Related);
      })
      .catch((exc) => !cancelled && setError(exc instanceof Error ? exc.message : String(exc)))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [url]);

  const top = related?.related[0]?.score ?? 1;

  return (
    <div className="graph-related">
      <aside className="graph-article-picker" aria-label="Articles in the graph">
        <label className="field-label" htmlFor="graph-article-search">
          Articles in the graph
        </label>
        <input
          id="graph-article-search"
          type="text"
          value={search}
          placeholder="Search title or URL"
          onChange={(event) => setSearch(event.target.value)}
        />
        <ul className="graph-article-list">
          {matches.map((article) => (
            <li key={article.url}>
              <button
                type="button"
                className={`graph-article${article.url === url ? " is-active" : ""}`}
                onClick={() => onPick(article.url)}
              >
                <span className="graph-article-title">
                  {article.title ? truncate(article.title, 80) : shortUrl(article.url)}
                </span>
                <span className="graph-article-meta">
                  {article.source ?? "?"} · {article.claims} claim{article.claims === 1 ? "" : "s"} ·{" "}
                  {article.entities} entities
                  {article.labelled ? " · hand-labelled" : ""}
                </span>
              </button>
            </li>
          ))}
          {matches.length === 0 && <li className="stats-muted">No article matches.</li>}
        </ul>
      </aside>

      <section className="graph-related-results">
        {!url && (
          <p className="graph-empty">
            Pick an article to see the others it is connected to - through a shared claim (3),
            a shared evidence page (1.5), a shared entity (2 ÷ how many articles mention it) or a
            shared topic (0.3).
          </p>
        )}

        {url && (
          <>
            <div className="graph-related-head">
              <div>
                <h2>{related?.title ?? shortUrl(url)}</h2>
                {safeHref(url) && (
                  <a className="card-url" href={safeHref(url)!} target="_blank" rel="noreferrer">
                    {url}
                  </a>
                )}
              </div>
              <button type="button" className="graph-secondary" onClick={() => onShowGraph(url)}>
                Show its graph
              </button>
            </div>

            {loading && (
              <p className="stats-muted">
                <span className="spinner" aria-hidden="true" /> Walking the graph…
              </p>
            )}
            {error && <div className="error-banner">{error}</div>}

            {related && !loading && related.related.length === 0 && (
              <p className="graph-empty">
                Nothing in the graph shares a claim, an evidence page, an entity or a topic with
                this article yet.
              </p>
            )}

            <ol className="graph-related-list">
              {related?.related.map((item) => (
                <li key={item.url} className="graph-related-item">
                  <div className="graph-related-row">
                    <div className="graph-related-title">
                      <a href={safeHref(item.url) ?? undefined} target="_blank" rel="noreferrer">
                        {item.title ? truncate(item.title, 90) : shortUrl(item.url)}
                      </a>
                      <span className="stats-muted">
                        {item.source ?? "?"}
                        {item.verdict ? " · " : ""}
                      </span>
                      {item.verdict && <VerdictBadge verdict={item.verdict as Verdict} />}
                    </div>
                    <div className="graph-score" title="Sum of the weights below">
                      <span className="graph-score-track">
                        <span
                          className="graph-score-fill"
                          style={{ width: `${Math.max(4, (item.score / top) * 100)}%` }}
                        />
                      </span>
                      <span className="stats-number">{item.score.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="chip-row">
                    {item.shared
                      .slice()
                      .sort((a, b) => b.weight - a.weight)
                      .slice(0, 12)
                      .map((shared) => (
                        <span key={`${shared.kind}-${shared.via}`} className={`chip graph-shared-${shared.kind}`}>
                          <strong>{KIND_LABELS[shared.kind]}:</strong> {truncate(shared.via, 60)}{" "}
                          <span className="stats-muted">+{shared.weight.toFixed(2)}</span>
                        </span>
                      ))}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </section>
    </div>
  );
}
