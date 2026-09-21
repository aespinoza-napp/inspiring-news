"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnalysisJob, PhaseEvent } from "@/lib/types";
import { useLiveJobs } from "@/lib/useLiveJobs";
import { buildTrace } from "@/lib/liveTrace";
import { LiveTrace } from "@/components/LiveTrace";
import { CURRENT_PHASE_LABELS } from "@/components/PhaseStepper";

export default function LivePage() {
  const { jobs, loading, error } = useLiveJobs();

  return (
    <>
      <h1>Live</h1>
      <p className="subtitle">
        Everything being verified right now, from any screen: what was
        searched, which sources came back, how each one was rated and what
        the model concluded — as it happens. Every step is also saved to the
        server, so a run that fails halfway still keeps what it found.
      </p>

      {error && <div className="error-banner">{error}</div>}

      {loading && !error && (
        <p className="trace-muted">
          <span className="spinner" aria-hidden="true" /> Connecting…
        </p>
      )}

      {!loading && !error && jobs.length === 0 && (
        <p className="live-empty">
          Nothing has run yet. Start an analysis on the Analyzer page, or check
          a claim — it will appear here while it works.
        </p>
      )}

      {jobs.map((job) => (
        <LiveJobCard key={job.jobId} job={job} />
      ))}
    </>
  );
}

function isActive(job: AnalysisJob) {
  return job.status === "queued" || job.status === "running";
}

function LiveJobCard({ job }: { job: AnalysisJob }) {
  const active = isActive(job);

  // Running jobs open themselves; finished ones stay a one-line summary
  // until asked for, since a long run is a lot to draw.
  const [open, setOpen] = useState(active);
  const [full, setFull] = useState<AnalysisJob | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // The list drops a job's events the moment it finishes, so keep the last
  // ones seen while it was running: the card must not blank out while the
  // full record is fetched.
  const lastSeen = useRef<PhaseEvent[]>([]);
  if (active) lastSeen.current = job.events;

  useEffect(() => {
    if (!open || active || full || (job.eventCount ?? 1) === 0) return;

    let cancelled = false;

    fetch(`/api/jobs/${job.jobId}`, { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (cancelled) return;
        if (!response.ok) {
          setLoadError(data?.error ?? data?.detail ?? `Request failed (${response.status})`);
          return;
        }
        setFull(data as AnalysisJob);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Something went wrong.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, active, full, job.jobId, job.eventCount]);

  const events = active ? job.events : full?.events ?? lastSeen.current;

  const trace = useMemo(() => buildTrace(events), [events]);

  const lastPhase = events[events.length - 1]?.phase;
  const isClaim = job.kind === "claim";

  const statusText =
    job.status === "failed"
      ? job.error ?? "Failed"
      : job.status === "done"
      ? "Complete"
      : lastPhase
      ? CURRENT_PHASE_LABELS[lastPhase] ?? lastPhase
      : "Queued…";

  return (
    <article className="card live-job">
      <header className="live-job-head">
        <span className={`live-kind live-kind-${isClaim ? "claim" : "article"}`}>
          {isClaim ? "Claim" : "Article"}
        </span>

        <div className="live-job-title">
          <h2>{isClaim ? job.url : trace.title ?? job.url}</h2>
          {!isClaim && trace.title && <span className="card-url">{job.url}</span>}
        </div>

        <span className={`live-status live-status-${job.status}`} role="status">
          {active && <span className="spinner" aria-hidden="true" />}
          {statusText}
        </span>
      </header>

      <div className="live-job-meta">
        {job.createdAt && (
          <span className="trace-muted">Started {clock(job.createdAt)}</span>
        )}

        <button
          type="button"
          className="live-toggle"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide details" : "Show details"}
        </button>
      </div>

      {open && (
        <>
          {loadError && <div className="error-banner">{loadError}</div>}
          <LiveTrace trace={trace} />
        </>
      )}
    </article>
  );
}

function clock(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
