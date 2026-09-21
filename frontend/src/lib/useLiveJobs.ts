"use client";

import { useEffect, useState } from "react";
import { AnalysisJob, LiveJobsResponse } from "@/lib/types";

const ACTIVE_POLL_MS = 1000;
const IDLE_POLL_MS = 3000;

interface UseLiveJobsResult {
  jobs: AnalysisJob[];
  /** True until the first response, so an empty list is not shown early. */
  loading: boolean;
  error: string | null;
}

/**
 * Follows every job the backend is running or has run recently, not one
 * this page started - so a second screen can watch verification happen.
 *
 * Polls a second apart while something is running and every three when
 * nothing is. Each poll is scheduled only after the previous one settles,
 * so a slow response can never pile requests up, and every reschedule is
 * guarded by `cancelled` - the same rule as useAnalysisJob, for the same
 * reason: a timer created after cleanup ran would poll forever with
 * nothing left to clear it.
 */
export function useLiveJobs(): UseLiveJobsResult {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      let anyActive = false;

      try {
        const response = await fetch("/api/jobs?limit=20", { cache: "no-store" });
        const data = await response.json();

        if (cancelled) return;

        if (!response.ok) {
          setError(data?.error ?? `Request failed (${response.status})`);
        } else {
          const list = (data as LiveJobsResponse).jobs ?? [];
          setJobs(list);
          setError(null);
          anyActive = list.some(
            (job) => job.status === "queued" || job.status === "running"
          );
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }

      if (cancelled) return;

      setLoading(false);
      timer = setTimeout(tick, anyActive ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    }

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { jobs, loading, error };
}
