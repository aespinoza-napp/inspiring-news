"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ScrapedArticles,
  ScrapedDomainStats,
  ScrapeOutcome,
  ScraperDomainStats,
  ScraperStats,
} from "@/lib/types";
import { DailyBars } from "@/components/DailyBars";
import { IngestPanel } from "@/components/IngestPanel";

// How often the counts refresh on their own. The page answers "is the
// scraper failing?", so it should show a run's requests as they happen,
// not only after a manual reload.
const REFRESH_MS = 10_000;

const OUTCOMES: { key: ScrapeOutcome; label: string; hint: string }[] = [
  { key: "ok", label: "OK", hint: "An article was extracted." },
  {
    key: "too_short",
    label: "Too short",
    hint: "Text came back but under the minimum length: a paywall, cookie wall or gallery page.",
  },
  {
    key: "no_content",
    label: "No content",
    hint: "The page loaded but no article text was found in it. Often a JavaScript-rendered page.",
  },
  { key: "http_error", label: "HTTP error", hint: "The server answered 4xx or 5xx." },
  { key: "timeout", label: "Timeout", hint: "No answer within the time limit." },
  {
    key: "connection_error",
    label: "Connection",
    hint: "The server could not be reached at all.",
  },
  {
    key: "blocked",
    label: "Blocked",
    hint: "Refused by our own URL guard (a private or reserved address). Never sent.",
  },
  { key: "error", label: "Other error", hint: "Anything else the strategy raised." },
  {
    key: "unavailable",
    label: "No browser",
    hint: "The page needed the headless browser step, which is not installed here.",
  },
];

const FAILURES = OUTCOMES.filter((outcome) => outcome.key !== "ok");

function percent(value: number | null): string {
  return value === null ? "–" : `${Math.round(value * 100)}%`;
}

function milliseconds(value: number | null): string {
  if (value === null) return "–";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

// "TrafilaturaStrategy" -> "Trafilatura", for display only.
function strategyName(name: string): string {
  return name.replace(/Strategy$/, "").replace(/Extraction$/, "");
}

function strategyList(counts: Record<string, number>): string {
  return Object.entries(counts)
    .sort(([, a], [, b]) => b - a)
    .map(([name, count]) => `${strategyName(name)} ${count}`)
    .join(" · ");
}

// Discovery strategies win too (the feed that produced the links), but
// they did not extract an article.
function extractionWinners(counts: Record<string, number>): Record<string, number> {
  return Object.fromEntries(
    Object.entries(counts).filter(([name]) => !name.endsWith("DiscoveryStrategy"))
  );
}

function when(iso: string | null): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

// A domain is flagged when most of what it was asked for failed, and it
// was asked enough times for that to mean something.
function health(row: ScraperDomainStats): "good" | "warn" | "bad" {
  if (row.successRate === null || row.extractions < 3) return "warn";
  if (row.successRate >= 0.8) return "good";
  if (row.successRate >= 0.4) return "warn";
  return "bad";
}

// Only http(s) URLs become links: they come from pages the server was
// asked to fetch, not from us.
function safeHref(url: string | null): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

const BROWSER = "PlaywrightExtractionStrategy";

/**
 * When every article from a domain came from the browser, the two cheap
 * attempts before it are spent for nothing on each page. The stats are
 * what show it; the fix is one line in the source's YAML.
 */
function javascriptHint(row: ScraperDomainStats): string | null {
  const winners = Object.keys(row.strategies);

  if (row.ok < 2 || winners.length !== 1 || winners[0] !== BROWSER) {
    return null;
  }

  const configured = row.sources.filter((source) => source !== "web");

  return configured.length > 0
    ? `Only the browser gets articles here. Set requires_javascript: true in ${configured
        .map((source) => `${source}.yaml`)
        .join(", ")} to skip the two cheap attempts.`
    : "Only the browser gets articles here. Add it as a source with requires_javascript: true to skip the two cheap attempts.";
}

function OutcomeChips({ row }: { row: ScraperDomainStats }) {
  const failures = FAILURES.filter(({ key }) => (row.outcomes[key] ?? 0) > 0);

  if (failures.length === 0) {
    return <span className="stats-muted">none</span>;
  }

  return (
    <span className="stats-chips">
      {failures.map(({ key, label, hint }) => (
        <span className={`stats-chip stats-chip-${key}`} key={key} title={hint}>
          {label} {row.outcomes[key]}
        </span>
      ))}
    </span>
  );
}

function DomainRow({ row }: { row: ScraperDomainStats }) {
  const href = safeHref(row.lastUrl);
  const rate = row.successRate ?? 0;

  return (
    <tr>
      <td>
        <div className="stats-domain">{row.domain}</div>
        <div className="stats-muted">
          {Object.entries(row.purposes)
            .map(([purpose, count]) => `${purpose} ${count}`)
            .join(" · ")}
        </div>
      </td>
      <td className="stats-number">
        {row.extractions}
        <div className="stats-muted">
          {row.requests} {row.requests === 1 ? "request" : "requests"}
        </div>
      </td>
      <td>
        <div className="stats-rate">
          <span className={`stats-rate-value stats-${health(row)}`}>
            {percent(row.successRate)}
          </span>
          <span className="stats-rate-track" aria-hidden="true">
            <span
              className={`stats-rate-fill stats-fill-${health(row)}`}
              style={{ width: `${Math.round(rate * 100)}%` }}
            />
          </span>
        </div>
        <div className="stats-muted">
          {row.ok} ok · {row.failed} failed
        </div>
        {Object.keys(row.strategies).length > 0 && (
          <div className="stats-muted" title="The strategy that produced the article">
            via {strategyList(row.strategies)}
          </div>
        )}
        {javascriptHint(row) && (
          <div className="stats-hint">{javascriptHint(row)}</div>
        )}
      </td>
      <td>
        <OutcomeChips row={row} />
      </td>
      <td className="stats-number">{milliseconds(row.avgMs)}</td>
      <td>
        <div>
          {row.lastOutcome ?? "–"}
          {row.lastStatus !== null && ` · ${row.lastStatus}`}
          <span className="stats-muted"> · {when(row.lastAt)}</span>
        </div>
        {href && (
          <a
            className="stats-url"
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            title={href}
          >
            {href}
          </a>
        )}
        {/* The last failure stays visible after the domain recovers:
            "why did it fail" is the question this page is opened for. */}
        {row.lastError && (
          <div className="stats-error" title={row.lastError}>
            Last failure ({when(row.lastErrorAt)}): {row.lastError}
          </div>
        )}
      </td>
    </tr>
  );
}

// "3 / 47" with the share, flagged when most articles arrived without it -
// a missing title silently weakens claim selection and fact-checking.
function Coverage({ have, of }: { have: number; of: number }) {
  if (of === 0) return <span className="stats-muted">–</span>;

  const share = have / of;
  const tone = share >= 0.8 ? "stats-good" : share >= 0.4 ? "stats-warn" : "stats-bad";

  return (
    <span className={tone}>
      {Math.round(share * 100)}%
      <span className="stats-muted"> ({have})</span>
    </span>
  );
}

function languages(row: ScrapedDomainStats): string {
  return Object.entries(row.languages)
    .sort(([, a], [, b]) => b - a)
    .map(([language, count]) => `${language} ${count}`)
    .join(" · ");
}

function ArticlesSection({ articles }: { articles: ScrapedArticles }) {
  const { totals } = articles;

  return (
    <section className="stats-section">
      <h2>Scraped articles</h2>
      <p className="claims-note">
        Articles the scraper fetched, extracted and stored in the lake, and
        what happened to them afterwards. Every analysis stores a new copy,
        so re-analysing an article counts it again under &quot;scraped&quot;
        but not under &quot;unique&quot;. Evidence pages are fetched but never
        stored, so they only show up in the requests above.
      </p>

      <div className="stats-totals">
        <div className="stats-total">
          <div className="stats-total-value">{totals.scraped}</div>
          <div className="stats-total-label">scraped</div>
        </div>
        <div className="stats-total">
          <div className="stats-total-value">{totals.uniqueUrls}</div>
          <div className="stats-total-label">unique articles</div>
        </div>
        <div className="stats-total">
          <div className="stats-total-value stats-good">{totals.publishable}</div>
          <div className="stats-total-label">publishable</div>
        </div>
        <div className="stats-total">
          <div className="stats-total-value">{totals.rejected}</div>
          <div className="stats-total-label">rejected</div>
        </div>
      </div>

      {totals.scraped > 0 && (
        <div className="card">
          <div className="section-label">Metadata the extractor found</div>
          <dl className="stats-coverage">
            <div>
              <dt>Title</dt>
              <dd>
                <Coverage have={totals.withTitle} of={totals.scraped} />
              </dd>
            </div>
            <div>
              <dt>Author</dt>
              <dd>
                <Coverage have={totals.withAuthor} of={totals.scraped} />
              </dd>
            </div>
            <div>
              <dt>Published date</dt>
              <dd>
                <Coverage have={totals.withDate} of={totals.scraped} />
              </dd>
            </div>
          </dl>
          {totals.withTitle < totals.scraped && (
            <p className="claims-note">
              Articles stored before the title fix (trafilatura&apos;s{" "}
              <code>with_metadata</code>) have no title, author or date. Analyse
              them again to refresh them.
            </p>
          )}

          <div className="section-label">Articles scraped per day</div>
          <DailyBars
            points={articles.daily.map((day) => ({
              date: day.date,
              value: day.scraped,
            }))}
            unit={["article", "articles"]}
            label="Articles scraped per day"
          />
        </div>
      )}

      {articles.domains.length > 0 && (
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>Domain</th>
                <th className="stats-number">Scraped</th>
                <th className="stats-number">Unique</th>
                <th className="stats-number">Title</th>
                <th className="stats-number">Author</th>
                <th className="stats-number">Date</th>
                <th className="stats-number">Avg length</th>
                <th>Then</th>
                <th>Scraped between</th>
              </tr>
            </thead>
            <tbody>
              {articles.domains.map((row) => (
                <tr key={row.domain}>
                  <td>
                    <div className="stats-domain">{row.domain}</div>
                    <div className="stats-muted">{languages(row)}</div>
                  </td>
                  <td className="stats-number">{row.scraped}</td>
                  <td className="stats-number">{row.uniqueUrls}</td>
                  <td className="stats-number">
                    <Coverage have={row.withTitle} of={row.scraped} />
                  </td>
                  <td className="stats-number">
                    <Coverage have={row.withAuthor} of={row.scraped} />
                  </td>
                  <td className="stats-number">
                    <Coverage have={row.withDate} of={row.scraped} />
                  </td>
                  <td className="stats-number">
                    {row.avgLength === null
                      ? "–"
                      : `${Math.round(row.avgLength).toLocaleString()} chars`}
                  </td>
                  <td>
                    <div>
                      {row.processed} processed · {row.stored} stored
                    </div>
                    <div className="stats-muted">
                      {row.publishable} publishable · {row.rejected} rejected
                    </div>
                  </td>
                  <td>
                    {row.firstScraped ?? "–"}
                    {row.lastScraped && row.lastScraped !== row.firstScraped && (
                      <div className="stats-muted">to {row.lastScraped}</div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function ScraperStatsPage() {
  const [stats, setStats] = useState<ScraperStats | null>(null);
  const [articles, setArticles] = useState<ScrapedArticles | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [onlyFailing, setOnlyFailing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    try {
      const [requests, stored] = await Promise.all(
        ["/api/scraper/stats", "/api/scraper/articles"].map(async (path) => {
          const response = await fetch(path, { cache: "no-store" });
          const data = await response.json();

          if (!response.ok) {
            throw new Error(
              data?.error ?? data?.detail ?? `Request failed (${response.status})`
            );
          }

          return data;
        })
      );

      setStats(requests);
      setArticles(stored);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    // Rescheduled only while mounted - the same guard useLiveJobs keeps,
    // so an unmount during a request cannot leave a timer running.
    async function tick() {
      await load();
      if (!cancelled) timer = setTimeout(tick, REFRESH_MS);
    }

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  const rows = (stats?.domains ?? []).filter(
    (row) => !onlyFailing || row.failed > 0
  );

  const totals = stats?.totals;

  return (
    <>
      <h1>Scraper</h1>
      <p className="subtitle">
        What the scraper asked for and what it got. Each page is tried with
        the cheapest strategy first (trafilatura, then BeautifulSoup on the
        same HTML, then a headless browser) and only escalates when the next
        step could help.
        Requests shows, per domain, every page wanted, the requests that
        took, which strategy did the work and why the rest failed. Scraped
        articles shows what was actually stored. Refreshes every{" "}
        {REFRESH_MS / 1000} seconds.
      </p>

      <IngestPanel onQueued={load} />

      <h2>Requests</h2>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {!stats && !error && <p className="claims-note">Loading the counts…</p>}

      {totals && (
        <div className="stats-totals">
          <div className="stats-total">
            <div className="stats-total-value">{totals.extractions}</div>
            <div className="stats-total-label">
              pages wanted · {totals.requests} requests
            </div>
          </div>
          <div className="stats-total">
            <div className="stats-total-value stats-good">{totals.ok}</div>
            <div className="stats-total-label">succeeded</div>
          </div>
          <div className="stats-total">
            <div
              className={`stats-total-value ${totals.failed > 0 ? "stats-bad" : ""}`}
            >
              {totals.failed}
            </div>
            <div className="stats-total-label">failed</div>
          </div>
          <div className="stats-total">
            <div className="stats-total-value">{totals.domains}</div>
            <div className="stats-total-label">domains</div>
          </div>
        </div>
      )}

      {totals && Object.keys(extractionWinners(totals.strategies)).length > 0 && (
        <p className="claims-note">
          Articles extracted by {strategyList(extractionWinners(totals.strategies))}.
        </p>
      )}

      {totals && totals.failed > 0 && (
        <div className="card">
          <div className="section-label">Why requests failed</div>
          <div className="stats-chips">
            {FAILURES.filter(({ key }) => (totals.outcomes[key] ?? 0) > 0).map(
              ({ key, label, hint }) => (
                <span className={`stats-chip stats-chip-${key}`} key={key} title={hint}>
                  {label} {totals.outcomes[key]}
                </span>
              )
            )}
          </div>
          <dl className="stats-legend">
            {FAILURES.filter(({ key }) => (totals.outcomes[key] ?? 0) > 0).map(
              ({ key, label, hint }) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{hint}</dd>
                </div>
              )
            )}
          </dl>
        </div>
      )}

      <div className="stats-toolbar">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={onlyFailing}
            onChange={(event) => setOnlyFailing(event.target.checked)}
          />
          Only domains with failures
        </label>
        <button type="button" onClick={load} disabled={loading}>
          {loading && <span className="spinner" aria-hidden="true" />}
          Refresh
        </button>
      </div>

      {stats && rows.length === 0 && (
        <p className="claims-note">
          {stats.domains.length === 0
            ? "No requests yet. Analyze an article, or check a URL on the Enrichment page, and its requests will show up here."
            : "No domain has a failed request."}
        </p>
      )}

      {rows.length > 0 && (
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>Domain</th>
                <th className="stats-number">Pages</th>
                <th>Success</th>
                <th>Failures</th>
                <th className="stats-number">Avg time</th>
                <th>Last request</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <DomainRow row={row} key={row.domain} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {stats && (
        <p className="claims-note">Counting since {when(stats.since)}.</p>
      )}

      {articles && <ArticlesSection articles={articles} />}
    </>
  );
}
