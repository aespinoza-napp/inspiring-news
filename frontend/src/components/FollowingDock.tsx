"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CURRENT_PHASE_LABELS } from "@/components/PhaseStepper";
import { Followed, clearFinished, isRunning, unfollow, updateFollowed, useFollowing } from "@/lib/following";
import { traceHref } from "@/lib/trace";
import { AnalysisJob } from "@/lib/types";

// Every few seconds while something runs; nothing at all once all is done.
const POLL_MS = 3000;

/**
 * The articles this browser sent to analysis, docked in a corner of every
 * operator page: what each is doing now, how it ended, and its run on
 * Live and its journey on Trace one click away. It answers "where did the
 * articles I just sent go?" without scrolling to the foot of Discover or
 * hunting through Live's list.
 *
 * Only running jobs are polled (GET /api/jobs/batch), rescheduled behind
 * `cancelled` like useAnalysisJob - a finished one is summarised once into
 * lib/following.ts and never asked about again. Hidden on the public
 * reader: Live and Trace are behind the password.
 */
export function FollowingDock() {
  const pathname = usePathname();
  const loaded = useFollowing();
  const items = loaded ?? [];
  const [open, setOpen] = useState(false);

  // The public reader: no dock, and no polling behind it either.
  const hidden = pathname === "/reader" || pathname.startsWith("/reader/");

  const running = items.filter(isRunning);
  const runningIds = running.map((item) => item.jobId).join(",");

  // Open on its own when something new is followed - that is the moment
  // the person wants to see it - and stay as they leave it otherwise.
  // Counted only once storage has been read: before that the list is
  // empty, and reading it would look like three new follows on every load.
  const seen = useRef<number | null>(null);
  useEffect(() => {
    if (loaded === null) return;
    if (seen.current !== null && loaded.length > seen.current) setOpen(true);
    seen.current = loaded.length;
  }, [loaded]);

  useEffect(() => {
    if (!runningIds || hidden) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const response = await fetch(`/api/jobs/batch?ids=${runningIds}`, { cache: "no-store" });
        if (response.ok) {
          const data = (await response.json()) as { jobs?: (AnalysisJob | { jobId: string; status: "not_found" })[] };
          if (cancelled) return;
          for (const job of data.jobs ?? []) absorb(job);
        }
      } catch {
        // The backend restarting: try again on the next tick.
      }

      if (cancelled) return;
      timer = setTimeout(poll, POLL_MS);
    }

    void poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [runningIds, hidden]);

  if (hidden || items.length === 0) return null;

  const done = items.length - running.length;

  return (
    <aside className={open ? "following-dock is-open" : "following-dock"} aria-label="Articles you are following">
      <button
        type="button"
        className="following-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {running.length > 0 && <span className="spinner" aria-hidden="true" />}
        <span>
          Following <strong>{items.length}</strong>
          {running.length > 0 && <> · {running.length} running</>}
          {done > 0 && <> · {done} done</>}
        </span>
        <span aria-hidden="true">{open ? "▾" : "▴"}</span>
      </button>

      {open && (
        <div className="following-panel">
          <div className="following-head">
            <span className="section-label">Sent to analysis</span>
            {done > 0 && (
              <button type="button" className="following-clear" onClick={clearFinished}>
                Clear finished
              </button>
            )}
          </div>

          <ol className="following-list">
            {items.map((item) => (
              <FollowedRow key={item.jobId} item={item} />
            ))}
          </ol>
        </div>
      )}
    </aside>
  );
}

function FollowedRow({ item }: { item: Followed }) {
  const running = isRunning(item);

  return (
    <li className="following-item">
      <div className="following-title" title={item.url}>
        {item.title || item.url}
      </div>

      <div className="following-status">
        {running ? (
          <>
            <span className="spinner" aria-hidden="true" />
            <span>{item.phase ? CURRENT_PHASE_LABELS[item.phase] ?? item.phase : "Queued…"}</span>
          </>
        ) : (
          <Outcome item={item} />
        )}
      </div>

      <div className="following-links">
        <Link href={`/live?job=${item.jobId}`}>Live</Link>
        <Link href={traceHref(item.jobId)}>Trace</Link>
        <button type="button" className="following-remove" aria-label="Stop following" onClick={() => unfollow(item.jobId)}>
          ×
        </button>
      </div>
    </li>
  );
}

function Outcome({ item }: { item: Followed }) {
  if (item.status === "not_found") return <span className="following-bad">No longer on the server</span>;
  if (item.status === "failed") return <span className="following-bad">Failed{item.error ? `: ${item.error}` : ""}</span>;
  if (item.validated === false) return <span className="following-muted">Rejected at admission</span>;
  if (item.publishable) return <span className="following-good">On the reader{item.verdict ? ` · ${verdictName(item.verdict)}` : ""}</span>;
  return <span className="following-muted">Withheld{item.verdict ? ` · ${verdictName(item.verdict)}` : ""}</span>;
}

function verdictName(verdict: string): string {
  return verdict.replace(/_/g, " ").toLowerCase();
}

/** One polled job into the followed summary: a phase while it runs, an outcome once it ends. */
function absorb(job: AnalysisJob | { jobId: string; status: "not_found" }) {
  if (job.status === "not_found") {
    updateFollowed(job.jobId, { status: "not_found" });
    return;
  }

  const full = job as AnalysisJob;

  if (full.status === "done" || full.status === "failed") {
    const result = full.result;
    updateFollowed(full.jobId, {
      status: full.status,
      phase: null,
      error: full.error,
      ...(result?.title ? { title: result.title } : {}),
      publishable: result?.storage?.publishable ?? null,
      validated: result?.validity ? result.validity.isValid : null,
      verdict: result?.factCheck?.foundVerdict ?? result?.factCheck?.overallVerdict ?? null,
    });
    return;
  }

  const phase = full.events[full.events.length - 1]?.phase ?? null;
  const title = full.events.find((event) => event.phase === "scraped")?.data?.title;

  updateFollowed(full.jobId, {
    status: full.status,
    phase,
    ...(typeof title === "string" && title ? { title } : {}),
  });
}
