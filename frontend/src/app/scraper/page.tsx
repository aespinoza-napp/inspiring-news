"use client";

import { useCallback, useEffect, useState } from "react";
import { ScrapeOutcome, ScraperDomainStats, ScraperStats } from "@/lib/types";

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
];

const FAILURES = OUTCOMES.filter((outcome) => outcome.key !== "ok");

function percent(value: number | null): string {
  return value === null ? "–" : `${Math.round(value * 100)}%`;
}

function milliseconds(value: number | null): string {
  if (value === null) return "–";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

function when(iso: string | null): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

// A domain is flagged when most of what it was asked for failed, and it
// was asked enough times for that to mean something.
function health(row: ScraperDomainStats): "good" | "warn" | "bad" {
  if (row.successRate === null || row.requests < 3) return "warn";
  if (row.successRate >= 0.8) return "good";
  if (row.successRate >= 0.4) return "warn";
  return "bad";
}

// Only http(s) URLs become links: they come from pages the server was
// asked to fetch, not from us.
function safeHref(url: string | null): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
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
      <td className="stats-number">{row.requests}</td>
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

export default function ScraperStatsPage() {
  const [stats, setStats] = useState<ScraperStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [onlyFailing, setOnlyFailing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    try {
      const response = await fetch("/api/scraper/stats", { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.error ?? data?.detail ?? `Request failed (${response.status})`
        );
      }

      setStats(data);
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
        Every page the scraper has requested, counted per domain: articles
        sent to the analyzer, evidence pages read for claims, and URLs
        checked on the Enrichment page. Each request is sorted by what it
        came to, so a source that has started failing shows up here
        instead of as an empty result. Refreshes every{" "}
        {REFRESH_MS / 1000} seconds.
      </p>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {!stats && !error && <p className="claims-note">Loading the counts…</p>}

      {totals && (
        <div className="stats-totals">
          <div className="stats-total">
            <div className="stats-total-value">{totals.requests}</div>
            <div className="stats-total-label">requests</div>
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
                <th className="stats-number">Requests</th>
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
    </>
  );
}
