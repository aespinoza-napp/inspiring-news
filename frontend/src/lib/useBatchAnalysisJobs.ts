"use client";

import { useEffect, useState } from "react";
import {
  AnalysisJob,
  AnalysisJobsBatchStatusResponse,
  BatchJobStatusEntry,
  CreateAnalysisJobsBatchResponse,
  ThresholdOverrides,
} from "@/lib/types";

const POLL_INTERVAL_MS = 1000;

interface UseBatchAnalysisJobsResult {
  jobsByUrl: Record<string, AnalysisJob | null>;
  error: string | null;
}

function isTerminal(status: string): boolean {
  return status === "done" || status === "failed";
}

/**
 * Bulk sibling of useAnalysisJob: submits every url in one
 * POST /analyze/jobs/batch call instead of one request per url, then
 * polls all of them in one GET /analyze/jobs/batch?ids=... call per
 * tick. Two urls that dedupe onto the same backend job (identical url,
 * or one already in flight) resolve to the same AnalysisJob object here
 * too - callers rendering per-url cards will just show identical results
 * for both.
 *
 * Same single-poll-then-cancelled-guarded-setInterval shape as
 * useAnalysisJob.ts, for the same reason: an effect cleanup racing the
 * first in-flight poll must not leak an interval nothing can ever clear.
 */
export function useBatchAnalysisJobs(
  urls: string[],
  forceRefresh: boolean,
  thresholds?: ThresholdOverrides
): UseBatchAnalysisJobsResult {
  const urlsKey = urls.join("\n");
  const thresholdsKey = JSON.stringify(thresholds ?? null);

  const [jobsByUrl, setJobsByUrl] = useState<Record<string, AnalysisJob | null>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (urls.length === 0) {
      setJobsByUrl({});
      setError(null);
      return;
    }

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    async function pollOnce(urlToJobId: Record<string, string>) {
      const jobIds = Array.from(new Set(Object.values(urlToJobId)));

      try {
        const response = await fetch(
          `/api/jobs/batch?ids=${jobIds.map(encodeURIComponent).join(",")}`
        );
        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
          if (intervalId) clearInterval(intervalId);
          return;
        }

        const byJobId = new Map<string, BatchJobStatusEntry>(
          (data as AnalysisJobsBatchStatusResponse).jobs.map((entry) => [
            entry.jobId,
            entry,
          ])
        );

        const next: Record<string, AnalysisJob | null> = {};
        let allTerminal = true;

        for (const [url, jobId] of Object.entries(urlToJobId)) {
          const entry = byJobId.get(jobId);

          if (!entry) {
            next[url] = null;
            allTerminal = false;
          } else if (entry.status === "not_found") {
            // Only happens after a backend restart (in-memory job
            // store). Synthesized as a terminal failure so rendering
            // doesn't need a third state and polling doesn't spin on
            // a job id the backend will never recognize again.
            next[url] = {
              jobId: entry.jobId,
              url,
              status: "failed",
              events: [],
              result: null,
              error: "Job not found (the backend may have restarted).",
            };
          } else {
            next[url] = entry;
            if (!isTerminal(entry.status)) allTerminal = false;
          }
        }

        setJobsByUrl(next);

        if (allTerminal && intervalId) {
          clearInterval(intervalId);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Something went wrong.");
          if (intervalId) clearInterval(intervalId);
        }
      }
    }

    async function start() {
      try {
        const response = await fetch("/api/jobs/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ urls, forceRefresh, thresholds }),
        });

        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
          return;
        }

        const urlToJobId: Record<string, string> = {};
        for (const entry of (data as CreateAnalysisJobsBatchResponse).jobs) {
          urlToJobId[entry.url] = entry.jobId;
        }

        await pollOnce(urlToJobId);

        // See useAnalysisJob.ts's identical check: the effect can be
        // cleaned up while the await above was in flight, and without
        // this the interval below would never be cleared by anything.
        if (cancelled) return;

        intervalId = setInterval(() => pollOnce(urlToJobId), POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Something went wrong.");
        }
      }
    }

    setJobsByUrl({});
    setError(null);
    start();

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
    // urlsKey/thresholdsKey, not `urls`/`thresholds`: both are given a
    // new identity on every render by the caller, which would restart
    // the batch in an endless loop.
  }, [urlsKey, forceRefresh, thresholdsKey]);

  return { jobsByUrl, error };
}
