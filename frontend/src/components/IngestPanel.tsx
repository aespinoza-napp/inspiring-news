"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IngestReport, IngestSource } from "@/lib/types";

const PER_SOURCE_OPTIONS = [1, 2, 3, 5, 10];

function methodName(method: string | null): string {
  if (!method) return "–";
  return method.includes("Trafilatura") ? "homepage / feed search" : "RSS feed";
}

/**
 * Discover articles from the configured sources and queue the new ones
 * for analysis. Nothing runs on a timer: every queued article is a full
 * analysis, so the button states the worst case before it is pressed.
 */
export function IngestPanel({ onQueued }: { onQueued?: () => void }) {
  const [sources, setSources] = useState<IngestSource[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [perSource, setPerSource] = useState(3);
  const [report, setReport] = useState<IngestReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch("/api/ingest/sources", { cache: "no-store" });
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
        }

        if (cancelled) return;

        setSources(data.sources);
        setSelected(new Set(data.sources.map((source: IngestSource) => source.id)));
        setReport(data.lastRun);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the sources.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function run() {
    setRunning(true);
    setError(null);

    try {
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sources: Array.from(selected),
          perSource,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
      }

      setReport(data);
      onQueued?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed.");
    } finally {
      setRunning(false);
    }
  }

  const maxJobs = selected.size * perSource;

  return (
    <section className="card ingest-panel">
      <div className="section-label">Ingest from sources</div>
      <p className="claims-note">
        Reads each source&apos;s feed (or finds one from its homepage), keeps
        links that look like articles and aren&apos;t already stored, and
        queues them for a full analysis. Follow the runs on{" "}
        <Link href="/live">Live</Link>. English sources are also pre-filtered
        by topic; the rest are left to the admission filter, which rejects
        off-topic articles before any LLM call.
      </p>

      {sources.length > 0 && (
        <div className="ingest-sources">
          {sources.map((source) => (
            <label className="checkbox-label" key={source.id}>
              <input
                type="checkbox"
                checked={selected.has(source.id)}
                onChange={() => toggle(source.id)}
              />
              {source.name}
              <span className="stats-muted"> {source.language}</span>
            </label>
          ))}
        </div>
      )}

      <div className="ingest-controls">
        <label className="ingest-per-source">
          Articles per source
          <select
            value={perSource}
            onChange={(event) => setPerSource(Number(event.target.value))}
          >
            {PER_SOURCE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <button type="button" onClick={run} disabled={running || selected.size === 0}>
          {running && <span className="spinner" aria-hidden="true" />}
          {running ? "Discovering…" : `Queue up to ${maxJobs} ${maxJobs === 1 ? "analysis" : "analyses"}`}
        </button>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {report && (
        <div className="ingest-report">
          <p className="claims-note">
            {report.totals.queued} queued · {report.totals.discovered} links found ·{" "}
            {report.totals.alreadyStored} already stored · {report.totals.deferred} left
            for next time
            {report.totals.failed > 0 && ` · ${report.totals.failed} sources found nothing`}{" "}
            <span className="stats-muted">
              ({new Date(report.startedAt).toLocaleString()})
            </span>
          </p>

          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Found via</th>
                  <th className="stats-number">Links</th>
                  <th className="stats-number">Stored</th>
                  <th className="stats-number">Queued</th>
                  <th className="stats-number">Deferred</th>
                  <th>Problem</th>
                </tr>
              </thead>
              <tbody>
                {report.sources.map((row) => (
                  <tr key={row.source}>
                    <td className="stats-domain">{row.name}</td>
                    <td>{methodName(row.method)}</td>
                    <td className="stats-number">{row.discovered}</td>
                    <td className="stats-number">{row.alreadyStored}</td>
                    <td className="stats-number">{row.queued.length}</td>
                    <td className="stats-number">{row.deferred}</td>
                    <td>
                      {row.error ? (
                        <div className="stats-error" title={row.error}>
                          {row.error}
                        </div>
                      ) : (
                        <span className="stats-muted">–</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
