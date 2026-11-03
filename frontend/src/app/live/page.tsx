"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnalysisJob, PhaseEvent } from "@/lib/types";
import { useLiveJobs } from "@/lib/useLiveJobs";
import { buildTrace } from "@/lib/liveTrace";
import { LiveTrace } from "@/components/LiveTrace";
import { CURRENT_PHASE_LABELS } from "@/components/PhaseStepper";
import { FlowSteps } from "@/components/FlowSteps";
import { WriteArticleLink } from "@/components/drafts/WriteArticleLink";
import { TraceLink } from "@/components/TraceLink";

const JOB_ID = /^[0-9a-f]{32}$/;

export default function LivePage() {
  const { jobs, loading, error } = useLiveJobs();

  // ?job=<id>: one run opened by link - from Trace, from Discover's queue,
  // from anywhere that holds a job id. The list holds only what this
  // process keeps in memory; a run from before a restart is still read by
  // id from the journal, so it is fetched on its own and pinned on top.
  const [focus, setFocus] = useState<string | null>(null);
  const [pinned, setPinned] = useState<AnalysisJob | null>(null);
  const [pinError, setPinError] = useState<string | null>(null);

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("job");
    if (id && JOB_ID.test(id)) setFocus(id);
  }, []);

  const listed = focus ? jobs.some((job) => job.jobId === focus) : false;

  useEffect(() => {
    if (!focus || loading || listed || pinned) return;

    let cancelled = false;

    fetch(`/api/jobs/${focus}`, { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (cancelled) return;
        if (!response.ok) {
          setPinError(data?.error ?? data?.detail ?? `No job ${focus} (${response.status}).`);
          return;
        }
        setPinned(data as AnalysisJob);
      })
      .catch((err) => {
        if (!cancelled) setPinError(err instanceof Error ? err.message : "Something went wrong.");
      });

    return () => {
      cancelled = true;
    };
  }, [focus, loading, listed, pinned]);

  return (
    <>
      <FlowSteps current="live" />

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

      {focus && (
        <p className="trace-muted">
          Showing the run opened by link first.{" "}
          <button
            type="button"
            className="live-toggle"
            onClick={() => {
              setFocus(null);
              setPinned(null);
              const url = new URL(window.location.href);
              url.searchParams.delete("job");
              window.history.replaceState(null, "", url.toString());
            }}
          >
            Show all as usual
          </button>
        </p>
      )}

      {pinError && <div className="error-banner">{pinError}</div>}

      {pinned && !listed && <LiveJobCard key={pinned.jobId} job={pinned} focused />}

      {[...jobs]
        // The focused run first, the rest in the backend's order.
        .sort((a, b) => Number(b.jobId === focus) - Number(a.jobId === focus))
        .map((job) => (
          <LiveJobCard key={job.jobId} job={job} focused={job.jobId === focus} />
        ))}
    </>
  );
}

function isActive(job: AnalysisJob) {
  return job.status === "queued" || job.status === "running";
}

function LiveJobCard({ job, focused = false }: { job: AnalysisJob; focused?: boolean }) {
  const active = isActive(job);

  // Running jobs open themselves, and so does the one opened by link;
  // finished ones stay a one-line summary until asked for, since a long
  // run is a lot to draw.
  const [open, setOpen] = useState(active || focused);
  const card = useRef<HTMLElement>(null);

  useEffect(() => {
    if (focused) card.current?.scrollIntoView({ block: "start" });
  }, [focused]);
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

  // The list drops a finished job's result; the full record (fetched on
  // "Show details") has it, and says whether the run was published.
  const result = full?.result ?? job.result;
  const writable = job.status === "done" && !isClaim && !!result?.storage?.publishable;

  const statusText =
    job.status === "failed"
      ? job.error ?? "Failed"
      : job.status === "done"
      ? "Complete"
      : lastPhase
      ? CURRENT_PHASE_LABELS[lastPhase] ?? lastPhase
      : "Queued…";

  return (
    <article ref={card} className={focused ? "card live-job is-focused" : "card live-job"}>
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

        {!isClaim && <TraceLink q={job.jobId} />}

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
          {writable && <WriteArticleLink url={result?.url || job.url} />}
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
