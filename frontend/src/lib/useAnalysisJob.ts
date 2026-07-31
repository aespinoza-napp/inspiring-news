"use client";

import { useEffect, useState } from "react";
import { AnalysisJob } from "@/lib/types";

const POLL_INTERVAL_MS = 1000;

interface UseAnalysisJobResult {
  job: AnalysisJob | null;
  error: string | null;
}

/**
 * Kicks off a background analysis job for `url` and polls its status
 * every second until it reaches a terminal state (done/failed). Restarts
 * whenever `url`/`forceRefresh` change, and stops polling on unmount.
 */
export function useAnalysisJob(
  url: string,
  forceRefresh: boolean
): UseAnalysisJobResult {
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
          body: JSON.stringify({ url, forceRefresh }),
        });

        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
          return;
        }

        await pollOnce(data.jobId);
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
  }, [url, forceRefresh]);

  return { job, error };
}
