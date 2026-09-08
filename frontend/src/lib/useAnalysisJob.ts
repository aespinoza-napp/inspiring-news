"use client";

import { useEffect, useState } from "react";
import { AnalysisJob, ThresholdOverrides } from "@/lib/types";

const POLL_INTERVAL_MS = 1000;

interface UseAnalysisJobResult {
  job: AnalysisJob | null;
  error: string | null;
}

/**
 * Kicks off a background analysis job for `url` and polls its status
 * every second until it reaches a terminal state (done/failed). Restarts
 * whenever `url`/`forceRefresh`/`thresholds` change, and stops polling on
 * unmount.
 *
 * `thresholds` overrides individual pipeline thresholds for this run only;
 * omit it (or omit any field) to use the backend's configured defaults.
 */
export function useAnalysisJob(
  url: string,
  forceRefresh: boolean,
  thresholds?: ThresholdOverrides
): UseAnalysisJobResult {
  const thresholdsKey = JSON.stringify(thresholds ?? null);

  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    async function pollOnce(jobId: string) {
      try {
        const response = await fetch(`/api/jobs/${jobId}`);
        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
          if (intervalId) clearInterval(intervalId);
          return;
        }

        setJob(data as AnalysisJob);

        if (data.status === "done" || data.status === "failed") {
          if (intervalId) clearInterval(intervalId);
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
        const response = await fetch("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, forceRefresh, thresholds }),
        });

        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
          return;
        }

        await pollOnce(data.jobId);

        // The effect can be cleaned up (component unmounted, url/forceRefresh
        // changed, or React 18 dev-mode Strict Mode's double-invoke) while
        // the await above was in flight. Without this check, the interval
        // created below would never be cleared by anything - the cleanup
        // function below already ran (it only exists once per effect
        // invocation), so this would poll forever in the background,
        // disconnected from the component and from the job's actual state.
        if (cancelled) return;

        intervalId = setInterval(() => pollOnce(data.jobId), POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Something went wrong.");
        }
      }
    }

    setJob(null);
    setError(null);
    start();

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
    // thresholdsKey, not `thresholds`: a caller passing an object
    // literal creates a new identity on every render, which would
    // restart the job in an endless loop.
  }, [url, forceRefresh, thresholdsKey]);

  return { job, error };
}
