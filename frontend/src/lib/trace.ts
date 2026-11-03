import { ReaderVerdictSummary } from "@/lib/reader";
import { Verdict } from "@/lib/types";

/**
 * One article's journey, as backend GET /trace returns it
 * (src/services/trace.py). Every stage's own record, joined by the
 * article's host and path - so any id a page shows can be pasted here.
 * Tolerant like lib/liveTrace.ts: a stage that predates a field leaves a
 * gap, never an exception.
 */

export interface TraceDiscovery {
  roundId: string;
  startedAt: string | null;
  edition: string;
  lens: string | null;
  groups: string[] | null;
  url: string;
  title: string | null;
  source: string | null;
  /** Place in the round's ranking, 1-based. */
  place: number;
  /** In the listed part (shown), else in the reserve "Show more" draws from. */
  shown: boolean;
  rank: { score?: number } | null;
  sameStoryAs: string | null;
  ai: { picked: boolean; score: number | null; reason: string | null; model: string | null } | null;
  queued: boolean;
  queuedAt: string | null;
  selectedBy: "ai" | "user" | "ai+user" | null;
  jobId: string | null;
  queueError: string | null;
}

export interface TraceJob {
  jobId: string;
  url: string;
  status: "queued" | "running" | "done" | "failed";
  createdAt: string;
  updatedAt: string;
  error: string | null;
  eventCount: number;
}

export interface TraceWrite {
  at: string;
  layer: "raw" | "processed" | "exploitation";
  recordId: string;
  parentLayer: string | null;
  parentRecordId: string | null;
}

export interface TraceRun {
  runId: string;
  articleId: string | null;
  url: string;
  contentHash: string | null;
  codeRevision: string | null;
  startedAt: string | null;
  pipelineVersion: string | null;
  components: Record<string, string>;
  thresholdOverrides: Record<string, unknown>;
  /** Every value the run used; empty on records from before 2026-11-03. */
  thresholds?: Record<string, unknown>;
  layers: Partial<Record<"raw" | "processed" | "exploitation", string>>;
  writes: TraceWrite[];
  reached: "exploitation" | "processed" | "raw" | "nothing readable";
  fetch: {
    extractor: string | null;
    fetchedAt: string | null;
    contentLength: number | null;
    title: string | null;
    language: string | null;
  } | null;
  outcome: {
    publishable: boolean;
    validationPassed: boolean;
    rejectionReasons: string[];
    isDuplicate: boolean;
    verdict: Verdict;
    verdictConfidence: number;
    claimsTotal: number;
    claimsChecked: number;
    primaryTopic: string | null;
    impactScore: number;
    citedEvidence: number;
  } | null;
}

export interface TraceDraft {
  id: string;
  title: string;
  status: "draft" | "approved" | "published";
  busy: string | null;
  edition: string;
  language: string;
  createdAt: string;
  updatedAt: string;
  revisions: number;
  published: { channel: string; at: string; url: string | null }[];
  storyId: string | null;
}

export interface ArticleTrace {
  key: string;
  resolvedFrom: "url" | "job" | "draft" | "reader";
  url: string | null;
  title: string | null;
  discovery: TraceDiscovery[];
  jobs: TraceJob[];
  runs: TraceRun[];
  reader: { published: boolean; id: string; title?: string | null; verdict?: ReaderVerdictSummary | null; checkedAt?: string | null } | null;
  drafts: TraceDraft[];
}

/** The page that follows one article: whatever id a page shows works. */
export function traceHref(q: string): string {
  return `/trace?q=${encodeURIComponent(q)}`;
}

/** A time a person reads at a glance: the date, then the time. */
export function when(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** The first characters of an id: enough to tell two apart, the rest on hover. */
export function short(id: string | null | undefined, length = 8): string {
  return id ? id.slice(0, length) : "–";
}

/** Whether the lake's lineage holds together, as backend GET /lake/integrity returns it. */
export interface LakeIntegrity {
  ok: boolean;
  records: Record<string, number>;
  runs: number;
  runsComplete: number;
  manifestEntries: number;
  errors: number;
  warnings: number;
  byKind: { severity: "error" | "warning"; kind: string; count: number }[];
  issues: {
    severity: "error" | "warning";
    kind: string;
    layer: string | null;
    recordId: string | null;
    url: string | null;
    detail: string;
  }[];
}
