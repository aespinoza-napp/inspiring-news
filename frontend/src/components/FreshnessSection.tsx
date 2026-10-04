"use client";

import { useCallback, useEffect, useState } from "react";
import { Freshness, FreshnessStat, FreshnessSummary } from "@/lib/types";

// How many of the newest articles are listed one by one.
const LISTED = 20;

/** Hours as minutes, hours or days, whichever reads best. */
function duration(hours: number | null): string {
  if (hours === null) return "–";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}

function Median({ stat }: { stat: FreshnessStat }) {
  if (stat.n === 0) return <span className="claims-note">–</span>;

  return (
    <span title={`median of ${stat.n}; 90th percentile ${duration(stat.p90)}`}>
      {duration(stat.median)}
      {stat.negative > 0 && (
        <span className="stats-bad" title="published after we fetched it: a wrong timezone or a rewritten feed time">
          {" "}
          ({stat.negative} negative)
        </span>
      )}
    </span>
  );
}

function when(iso: string | null): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

const FROM_LABEL: Record<string, string> = {
  feed: "feed",
  page: "page",
  date: "date only",
};

function Precision({ totals }: { totals: FreshnessSummary }) {
  const { feed, page, date, none } = totals.publishedFrom;
  return (
    <>
      {feed} feed · {page} page · {date} date only · {none} none
    </>
  );
}

/**
 * How long articles take to reach us after they are published
 * (GET /api/scraper/freshness). Loaded once and on demand, not on the
 * page's 10-second poll: it reads the whole lake.
 */
export function FreshnessSection() {
  const [data, setData] = useState<Freshness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);

    try {
      const response = await fetch("/api/scraper/freshness", { cache: "no-store" });
      const body = await response.json();

      if (!response.ok) {
        throw new Error(body?.error ?? body?.detail ?? `Request failed (${response.status})`);
      }

      setData(body as Freshness);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totals = data?.totals;

  return (
    <section className="stats-section">
      <h2>Time to reception</h2>
      <p className="claims-note">
        How long an article takes to reach us after it is published. The publication time comes from the
        feed item, or from the page&apos;s own <code>article:published_time</code>; an article that states only a
        date is counted in days, apart. <b>Seen</b> is published → first discovered by ingestion,{" "}
        <b>queue</b> is discovered → fetched, <b>reception</b> is published → fetched, and{" "}
        <b>on the reader</b> is published → publishable. Ingestion runs only when someone presses Ingest, so
        &quot;seen&quot; is mostly the time until the next press; queue and processing are the pipeline&apos;s own.
      </p>

      <button type="button" onClick={load} disabled={loading}>
        {loading ? "Reading the lake…" : "Refresh"}
      </button>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {totals && totals.articles === 0 && (
        <p className="claims-note">No article in the lake yet.</p>
      )}

      {totals && totals.articles > 0 && (
        <>
          <div className="stats-totals">
            <div className="stats-total">
              <div className="stats-total-value">
                <Median stat={totals.hours.reception} />
              </div>
              <div className="stats-total-label">
                median reception · p90 {duration(totals.hours.reception.p90)}
              </div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">
                <Median stat={totals.hours.queue} />
              </div>
              <div className="stats-total-label">median queue (ours)</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">
                <Median stat={totals.hours.available} />
              </div>
              <div className="stats-total-label">median until on the reader</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">{totals.articles}</div>
              <div className="stats-total-label">
                articles · {totals.ingested} ingested
              </div>
            </div>
          </div>

          <p className="claims-note">
            Publication time from: <Precision totals={totals} />.
            {totals.noTimezone > 0 && ` ${totals.noTimezone} page time(s) gave no timezone and may be hours off.`}
            {totals.receptionDays.n > 0 &&
              ` Date-only articles: median ${totals.receptionDays.median} day(s) from publication to fetch.`}
            {data && ` ${data.sightings} URL(s) seen by ingestion so far.`}
          </p>

          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th className="stats-number">Articles</th>
                  <th>Publication time from</th>
                  <th className="stats-number">Seen</th>
                  <th className="stats-number">Queue</th>
                  <th className="stats-number">Reception</th>
                  <th className="stats-number">On the reader</th>
                  <th className="stats-number">Date only (days)</th>
                </tr>
              </thead>
              <tbody>
                {data!.sources.map((row) => (
                  <tr key={row.source}>
                    <td>{row.source}</td>
                    <td className="stats-number">{row.articles}</td>
                    <td>
                      <Precision totals={row} />
                    </td>
                    <td className="stats-number">
                      <Median stat={row.hours.seen} />
                    </td>
                    <td className="stats-number">
                      <Median stat={row.hours.queue} />
                    </td>
                    <td className="stats-number">
                      <Median stat={row.hours.reception} />
                    </td>
                    <td className="stats-number">
                      <Median stat={row.hours.available} />
                    </td>
                    <td className="stats-number">
                      {row.receptionDays.n > 0 ? row.receptionDays.median : "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section-label">Newest {Math.min(LISTED, data!.articles.length)} articles</div>
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Published</th>
                  <th>Fetched</th>
                  <th className="stats-number">Reception</th>
                  <th>Via</th>
                </tr>
              </thead>
              <tbody>
                {data!.articles.slice(0, LISTED).map((row) => (
                  <tr key={row.key}>
                    <td>
                      <span title={row.url}>{row.title || row.url}</span>
                      <div className="claims-note">{row.sourceId ?? row.domain}</div>
                    </td>
                    <td>
                      {row.publishedFrom === "date" ? row.publishedAt : when(row.publishedAt)}
                      {row.publishedFrom && (
                        <div className="claims-note">
                          {FROM_LABEL[row.publishedFrom]}
                          {row.noTimezone && " · no timezone"}
                        </div>
                      )}
                    </td>
                    <td>{when(row.fetchedAt)}</td>
                    <td className="stats-number">
                      {row.lagHours.reception !== null
                        ? duration(row.lagHours.reception)
                        : row.receptionDays !== null
                          ? `${row.receptionDays} d`
                          : "–"}
                    </td>
                    <td>{row.via}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
