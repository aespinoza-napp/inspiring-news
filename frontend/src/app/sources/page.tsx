"use client";

import { useEffect, useState } from "react";
import {
  CheckableSource,
  SourceCheckReport,
  SourceCheckRow,
  SourceCheckSample,
  SourceVerdict,
} from "@/lib/types";

const PER_SOURCE_OPTIONS = [1, 2, 3, 5];

const VERDICTS: Record<SourceVerdict, { label: string; className: string; hint: string }> = {
  ok: {
    label: "Working",
    className: "stats-good",
    hint: "Every sample extracted with a title, author and date.",
  },
  partial: {
    label: "Partial",
    className: "stats-warn",
    hint: "Some samples failed, or extracted without a title, author or date.",
  },
  broken: {
    label: "Broken",
    className: "stats-bad",
    hint: "No links discovered, or not one sample extracted.",
  },
};

function methodName(method: string | null): string {
  if (!method) return "nothing found";
  return method.includes("Trafilatura") ? "homepage / feed search" : "RSS feed";
}

function strategyName(strategy: string | null): string {
  if (!strategy) return "–";
  return strategy.replace(/(Extraction)?Strategy$/, "");
}

function seconds(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

/** A metadata cell: the value, or a visible "missing" when the article had none. */
function Field({ value, extracted }: { value: string | null; extracted: boolean }) {
  if (value) return <span>{value}</span>;
  if (!extracted) return <span className="stats-muted">–</span>;
  return <span className="stats-bad">missing</span>;
}

function SampleRow({ sample }: { sample: SourceCheckSample }) {
  const extracted = sample.outcome === "ok";

  return (
    <tr>
      <td>
        <a className="stats-url" href={sample.url} target="_blank" rel="noreferrer" title={sample.url}>
          {sample.url.replace(/^https?:\/\/(www\.)?/, "")}
        </a>
      </td>
      <td>
        <span className={`stats-chip stats-chip-${sample.outcome}`}>
          {sample.outcome}
          {sample.status ? ` ${sample.status}` : ""}
        </span>
        {!extracted && sample.error && (
          <div className="stats-error" title={sample.error}>
            {sample.error}
          </div>
        )}
      </td>
      <td title={sample.tried.join(" → ")}>{strategyName(sample.strategy)}</td>
      <td className="source-check-title">
        <Field value={sample.title} extracted={extracted} />
      </td>
      <td>
        <Field value={sample.author} extracted={extracted} />
      </td>
      <td>
        <Field
          value={sample.publishedAt ? new Date(sample.publishedAt).toLocaleDateString() : null}
          extracted={extracted}
        />
      </td>
      <td className="stats-number">{extracted ? sample.bodyLength.toLocaleString() : "–"}</td>
      <td className="stats-number">{seconds(sample.elapsedMs)}</td>
    </tr>
  );
}

function SourceCard({
  row,
  onRecheck,
  rechecking,
}: {
  row: SourceCheckRow;
  onRecheck: () => void;
  rechecking: boolean;
}) {
  const verdict = VERDICTS[row.verdict];

  return (
    <section className="card source-check-card">
      <div className="source-check-head">
        <div>
          <h2>
            {row.name}{" "}
            <span className={`source-check-verdict ${verdict.className}`} title={verdict.hint}>
              {verdict.label}
            </span>
          </h2>
          <p className="stats-muted">
            {row.source}.yaml · {row.language}
            {!row.enabled && " · disabled"}
            {row.requiresJavascript && " · requires JavaScript"} ·{" "}
            <a href={row.baseUrl} target="_blank" rel="noreferrer">
              {row.baseUrl}
            </a>
          </p>
        </div>
        <button type="button" onClick={onRecheck} disabled={rechecking}>
          {rechecking && <span className="spinner" aria-hidden="true" />}
          {rechecking ? "Checking…" : "Re-check"}
        </button>
      </div>

      <p className="claims-note">
        Discovery: <strong>{row.discovery.found}</strong> article links via{" "}
        {methodName(row.discovery.method)}
        {row.rssUrl && (
          <>
            {" "}
            (<a href={row.rssUrl} target="_blank" rel="noreferrer">feed</a>)
          </>
        )}{" "}
        <span className="stats-muted">in {seconds(row.elapsedMs)} overall</span>
      </p>

      {row.discovery.error && <div className="stats-error source-check-discovery-error">{row.discovery.error}</div>}

      {row.samples.length > 0 && (
        <div className="stats-table-wrap">
          <table className="stats-table">
            <thead>
              <tr>
                <th>Article</th>
                <th>Outcome</th>
                <th>Strategy</th>
                <th>Title</th>
                <th>Author</th>
                <th>Date</th>
                <th className="stats-number">Characters</th>
                <th className="stats-number">Time</th>
              </tr>
            </thead>
            <tbody>
              {row.samples.map((sample) => (
                <SampleRow key={sample.url} sample={sample} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/**
 * Checks every configured source YAML: does discovery find article links,
 * and does the extraction cascade turn a few of them into an article with
 * a title, author and date? Nothing is stored or analysed.
 */
export default function SourcesPage() {
  const [sources, setSources] = useState<CheckableSource[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [perSource, setPerSource] = useState(2);
  const [report, setReport] = useState<SourceCheckReport | null>(null);
  const [running, setRunning] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch("/api/sources/check", { cache: "no-store" });
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
        }

        if (cancelled) return;

        setSources(data.sources);
        setSelected(new Set(data.sources.map((source: CheckableSource) => source.id)));
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

  async function check(ids: string[]) {
    setRunning((current) => new Set([...Array.from(current), ...ids]));
    setError(null);

    try {
      const response = await fetch("/api/sources/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: ids, perSource }),
      });

      const data: SourceCheckReport = await response.json();

      if (!response.ok) {
        const failure = data as unknown as { error?: string; detail?: string };
        throw new Error(failure.error ?? failure.detail ?? `Request failed (${response.status})`);
      }

      // A re-check of one source replaces only its row, so the rest of
      // the last full check stays on screen.
      setReport((current) => {
        if (!current || ids.length === sources.length) return data;

        const fresh = new Map(data.sources.map((row) => [row.source, row]));
        const rows = current.sources.map((row) => fresh.get(row.source) ?? row);

        for (const row of data.sources) {
          if (!current.sources.some((existing) => existing.source === row.source)) rows.push(row);
        }

        rows.sort((a, b) => a.source.localeCompare(b.source));

        return {
          ...data,
          sources: rows,
          totals: {
            sources: rows.length,
            ok: rows.filter((row) => row.verdict === "ok").length,
            partial: rows.filter((row) => row.verdict === "partial").length,
            broken: rows.filter((row) => row.verdict === "broken").length,
          },
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The check failed.");
    } finally {
      setRunning((current) => {
        const next = new Set(current);
        ids.forEach((id) => next.delete(id));
        return next;
      });
    }
  }

  const busy = running.size > 0;

  return (
    <>
      <h1>Sources</h1>
      <p className="subtitle">
        Checks each source YAML in <code>backend/data/sources</code> end to end: reads its feed
        (or finds one from its homepage), then extracts a few of the article links it finds with
        the same cascade the analyzer uses. Nothing is stored or analysed. Disabled sources are
        checked too.
      </p>

      <section className="card">
        <div className="section-label">Sources to check</div>

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
                <span className="stats-muted">
                  {" "}
                  {source.language}
                  {!source.enabled && " · disabled"}
                </span>
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

          <button
            type="button"
            onClick={() => check(Array.from(selected))}
            disabled={busy || selected.size === 0}
          >
            {busy && <span className="spinner" aria-hidden="true" />}
            {busy
              ? "Checking…"
              : `Check ${selected.size} ${selected.size === 1 ? "source" : "sources"}`}
          </button>
        </div>

        <p className="stats-muted">
          Takes up to a minute: every site is fetched for real, a few at a time.
        </p>
      </section>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {report && (
        <>
          <div className="stats-totals">
            <div className="stats-total">
              <div className="stats-total-value">{report.totals.sources}</div>
              <div className="stats-total-label">sources checked</div>
            </div>
            {(Object.keys(VERDICTS) as SourceVerdict[]).map((key) => (
              <div className="stats-total" key={key} title={VERDICTS[key].hint}>
                <div className={`stats-total-value ${VERDICTS[key].className}`}>
                  {report.totals[key]}
                </div>
                <div className="stats-total-label">{VERDICTS[key].label.toLowerCase()}</div>
              </div>
            ))}
          </div>

          <p className="stats-muted">
            Last check {new Date(report.startedAt).toLocaleString()}, {report.perSource} per source.
          </p>

          {report.sources.map((row) => (
            <SourceCard
              key={row.source}
              row={row}
              rechecking={running.has(row.source)}
              onRecheck={() => check([row.source])}
            />
          ))}
        </>
      )}
    </>
  );
}
