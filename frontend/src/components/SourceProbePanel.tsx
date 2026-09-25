"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ProbeSource, ProbeState, ProbeStatus } from "@/lib/types";

const PER_SOURCE_OPTIONS = [0, 3, 5, 10, 20];

const POLL_MS = 2000;

const STATUS_LABEL: Record<ProbeStatus, string> = {
  up: "Up",
  degraded: "Degraded",
  down: "Down",
};

const STATUS_CLASS: Record<ProbeStatus, string> = {
  up: "stats-good",
  degraded: "stats-warn",
  down: "stats-bad",
};

function feedName(method: string | null): string {
  if (!method) return "none";
  return method.includes("Trafilatura") ? "found from homepage" : "RSS";
}

// Feed entries and section-page links are other sites' HTML: only an
// http(s) URL becomes a link (the same rule as LiveTrace's safeHref).
function safeHref(url: string): string | undefined {
  return /^https?:\/\//i.test(url) ? url : undefined;
}

function pathOf(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

/**
 * Checks every source on demand: its feed, its topic section pages, and a
 * sample of real extractions - plus whether SearXNG's engines answer at
 * all. The run happens on the backend; this polls for it while it runs.
 */
export function SourceProbePanel() {
  const [state, setState] = useState<ProbeState | null>(null);
  const [perSource, setPerSource] = useState(5);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<ProbeState | null> => {
    try {
      const response = await fetch("/api/scraper/probe", { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
      }

      setState(data);
      setError(data.error ? `The last probe failed: ${data.error}` : null);

      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the probe.");
      return null;
    }
  }, []);

  // Load once; then, only while a probe runs, poll until it finishes.
  const running = state?.running ?? false;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      const next = await load();
      // Rescheduled only behind `cancelled`: a cleanup that fires while
      // the fetch is in flight must not leave a timer nobody clears
      // (frontend/CLAUDE.md, the useAnalysisJob incident).
      if (!cancelled && next?.running) {
        timer = setTimeout(tick, POLL_MS);
      }
    }

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load, running]);

  async function start() {
    setError(null);

    try {
      const response = await fetch("/api/scraper/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ perSource }),
      });

      const data = await response.json();

      if (!response.ok && response.status !== 409) {
        throw new Error(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
      }

      // 409 means one is already running: the state is still worth showing.
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The probe could not start.");
    }
  }

  function toggle(id: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const report = state?.report;
  const searchDown = report?.search?.filter((check) => !check.ok) ?? [];

  return (
    <section className="card probe-panel">
      <div className="section-label">Source health</div>
      <p className="claims-note">
        Asks every source, now: does its feed give article links, how many
        more do its topic section pages (<code>/science/</code>,{" "}
        <code>/ciencia/</code>…) add, and can a sample of those articles
        actually be extracted? When a feed is dead, the topic pages are how
        ingestion still finds articles. Also sends one query to SearXNG per
        language: every fact check&apos;s evidence depends on it.
      </p>

      <div className="ingest-controls">
        <label className="ingest-per-source">
          Articles extracted per source
          <select
            value={perSource}
            onChange={(event) => setPerSource(Number(event.target.value))}
            disabled={running}
          >
            {PER_SOURCE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === 0 ? "0 (links only)" : option}
              </option>
            ))}
          </select>
        </label>

        <button type="button" onClick={start} disabled={running}>
          {running && <span className="spinner" aria-hidden="true" />}
          {running ? "Probing sources…" : "Probe all sources"}
        </button>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {!report && !running && !error && (
        <p className="claims-note">No probe has run yet.</p>
      )}

      {report && (
        <>
          {searchDown.length > 0 && (
            <div className="error-banner" role="alert">
              Web search is returning nothing
              {searchDown.map((check) => (
                <span key={check.language}>
                  {" "}
                  · {check.language}:{" "}
                  {check.error ??
                    (check.unresponsive ?? [])
                      .map((engine) => `${engine.engine} (${engine.reason})`)
                      .join(", ")}
                </span>
              ))}
              . Claims will come back unverified until the engines answer.
            </div>
          )}

          <div className="stats-totals probe-totals">
            <div className="stats-total">
              <div className="stats-total-value stats-good">{report.totals.up}</div>
              <div className="stats-total-label">up</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value stats-warn">{report.totals.degraded}</div>
              <div className="stats-total-label">degraded</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value stats-bad">{report.totals.down}</div>
              <div className="stats-total-label">down</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">{report.totals.feedLinks}</div>
              <div className="stats-total-label">links from feeds</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">+{report.totals.extraLinks}</div>
              <div className="stats-total-label">more from topic pages</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">
                {report.totals.extracted}/{report.totals.sampled}
              </div>
              <div className="stats-total-label">sampled articles extracted</div>
            </div>
          </div>

          <p className="claims-note stats-muted">
            Last run {new Date(report.startedAt).toLocaleString()} ·{" "}
            {report.perSource} articles per source · click a source for its
            sections and sample
          </p>

          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Homepage</th>
                  <th>Feed</th>
                  <th className="stats-number">Feed links</th>
                  <th className="stats-number">+ Topic pages</th>
                  <th className="stats-number">Extracted</th>
                  <th>Why</th>
                </tr>
              </thead>
              <tbody>
                {report.sources.map((row) => (
                  <Fragment key={row.source}>
                    <tr className="probe-row" onClick={() => toggle(row.source)}>
                      <td className="stats-domain">
                        <button
                          type="button"
                          className="probe-toggle"
                          aria-expanded={open.has(row.source)}
                        >
                          {open.has(row.source) ? "▾" : "▸"} {row.name}
                        </button>
                        <span className="stats-muted"> {row.language}</span>
                      </td>
                      <td className={STATUS_CLASS[row.status]}>{STATUS_LABEL[row.status]}</td>
                      <td className={row.homepageError ? "stats-bad" : undefined}>
                        {row.homepageStatus ?? row.homepageError ?? "–"}
                      </td>
                      <td>{feedName(row.feedMethod)}</td>
                      <td className="stats-number">{row.feedLinks}</td>
                      <td className="stats-number">+{row.extraLinks}</td>
                      <td className="stats-number">
                        {row.sampled ? `${row.extracted}/${row.sampled}` : "–"}
                      </td>
                      <td>
                        <div className="probe-reason">{row.reason}</div>
                      </td>
                    </tr>
                    {open.has(row.source) && (
                      <tr className="probe-detail">
                        <td colSpan={8}>
                          <ProbeDetail row={row} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function ProbeDetail({ row }: { row: ProbeSource }) {
  return (
    <div className="probe-detail-grid">
      <div>
        <div className="section-label">Topic section pages</div>
        {row.sections.length === 0 ? (
          <p className="claims-note">None read{row.homepageError ? " – the homepage refused us" : ""}.</p>
        ) : (
          <ul className="probe-list">
            {row.sections.map((section) => (
              <li key={section.url}>
                <a href={safeHref(section.url)} target="_blank" rel="noreferrer">
                  {pathOf(section.url)}
                </a>{" "}
                <span className="stats-muted">{section.advertised ? "linked" : "guessed"}</span>{" "}
                {section.error && section.outcome !== "ok" ? (
                  <span className="stats-bad">{section.error}</span>
                ) : (
                  <span className={section.links ? "stats-good" : "stats-muted"}>
                    {section.links} links
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="section-label">Sampled articles</div>
        {row.sample.length === 0 ? (
          <p className="claims-note">None extracted.</p>
        ) : (
          <ul className="probe-list">
            {row.sample.map((item) => (
              <li key={item.url}>
                <span className={item.ok ? "stats-good" : "stats-bad"}>{item.ok ? "✓" : "✗"}</span>{" "}
                <a href={safeHref(item.url)} target="_blank" rel="noreferrer" className="probe-url">
                  {pathOf(item.url)}
                </a>{" "}
                <span className="stats-muted">
                  {item.via === "feed" ? "feed" : "topic page"}
                  {item.ok
                    ? ` · ${item.chars.toLocaleString()} chars · ${[
                        item.title && "title",
                        item.author && "author",
                        item.date && "date",
                      ]
                        .filter(Boolean)
                        .join(", ") || "no metadata"}`
                    : ` · ${item.error ?? item.outcome}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
