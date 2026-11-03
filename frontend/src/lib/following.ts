"use client";

import { useEffect, useState } from "react";

/**
 * The articles this browser sent to analysis and is following
 * (components/FollowingDock.tsx): from Discover's queue and the Analyze
 * page. A per-viewer convenience, so localStorage - every read and write
 * guarded, since storage can be blocked or absent; the dock then simply
 * starts empty. Not a record of anything: the jobs, their journal and
 * Trace are.
 *
 * A finished job keeps the little the dock shows (status, outcome) here,
 * so it is never polled again: a finished job's full record is hundreds of
 * KB, and only the running ones are asked about.
 */

export interface Followed {
  jobId: string;
  url: string;
  title?: string | null;
  /** Where it was sent from: "discover", "analyze". */
  from: string;
  addedAt: string;
  status?: "queued" | "running" | "done" | "failed" | "not_found";
  /** The last phase seen while it ran, for its one-line status. */
  phase?: string | null;
  /** Once done: whether the reader publishes it, and its verdict. */
  publishable?: boolean | null;
  verdict?: string | null;
  validated?: boolean | null;
  error?: string | null;
}

const KEY = "inspiring.following.v1";
const EVENT = "inspiring-following-change";

// The dock is a glance, not an archive.
const KEEP = 30;

export function readFollowing(): Followed[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item.jobId === "string") : [];
  } catch {
    return [];
  }
}

function write(items: Followed[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items.slice(0, KEEP)));
  } catch {
    // Blocked storage: the dock lives for this page only.
  }
  window.dispatchEvent(new Event(EVENT));
}

/** Follow these jobs, newest first; one already followed keeps its place and gains a title if it had none. */
export function follow(items: Omit<Followed, "addedAt">[]): void {
  const current = readFollowing();
  const known = new Map(current.map((item) => [item.jobId, item]));
  const added: Followed[] = [];

  for (const item of items) {
    if (!item.jobId) continue;
    const existing = known.get(item.jobId);
    if (existing) {
      if (!existing.title && item.title) existing.title = item.title;
      continue;
    }
    added.push({ ...item, addedAt: new Date().toISOString() });
  }

  write([...added, ...current]);
}

export function updateFollowed(jobId: string, patch: Partial<Followed>): void {
  const current = readFollowing();
  const item = current.find((entry) => entry.jobId === jobId);

  // Polled every few seconds: write (and re-render every listener) only
  // when something actually moved.
  if (!item || Object.entries(patch).every(([key, value]) => item[key as keyof Followed] === value)) return;

  write(current.map((entry) => (entry.jobId === jobId ? { ...entry, ...patch } : entry)));
}

export function unfollow(jobId: string): void {
  write(readFollowing().filter((item) => item.jobId !== jobId));
}

export function clearFinished(): void {
  write(readFollowing().filter((item) => item.status !== "done" && item.status !== "failed" && item.status !== "not_found"));
}

/**
 * The list, kept in step across components and tabs; null until storage
 * has been read, so "the list grew" is never mistaken for "it loaded".
 */
export function useFollowing(): Followed[] | null {
  const [items, setItems] = useState<Followed[] | null>(null);

  useEffect(() => {
    const refresh = () => setItems(readFollowing());
    refresh();
    window.addEventListener(EVENT, refresh);
    // Another tab following or finishing a job.
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  return items;
}

export function isRunning(item: Followed): boolean {
  return !item.status || item.status === "queued" || item.status === "running";
}
