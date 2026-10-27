// The writing flow's shapes (docs/decisions/writing.md). Mirrors
// backend/src/models/writer/draft.py exactly - keep the two in step, as
// lib/types.ts is kept with the analysis responses.

import { CorrectionMetric } from "@/lib/types";

export type DraftLanguage = "ca" | "es" | "en";

export type DraftStatus = "draft" | "approved" | "published";

export type DraftBusy = "generating" | "reviewing" | "rewriting" | "publishing";

// `restored` is a person putting an earlier revision's text back
// (POST /drafts/{id}/restore); its `model` is the one that wrote that text.
export type RevisionReason = "generated" | "edited" | "corrected" | "rewritten" | "restored";

// "angle": a source behind a constructive angle the fact-check confirmed,
// for a draft from a trend (docs/decisions/trends.md).
export type SourceOrigin = "analysed" | "related" | "evidence" | "angle";

export interface DraftSource {
  url: string;
  title: string;
  domain: string;
  origin: SourceOrigin;
  publishedAt: string | null;
  excerpt: string;
  reliabilityKnown: boolean;
}

export interface DraftFactCheck {
  claim: string;
  verdict: string;
  confidence: number | null;
  sourceUrls: string[];
}

export interface DraftMetadata {
  slug: string;
  seoDescription: string;
  keywords: string[];
  topic: string | null;
  tags: string[];
}

export interface DraftContent {
  title: string;
  subtitle: string;
  /** Markdown; [n] cites sources[n - 1]. */
  body: string;
}

export interface DraftReview {
  /** The corrector's metrics by name, plus whatever the draft review adds. */
  metrics: Record<string, CorrectionMetric>;
  /** The corrector's proposal; never applied without a person. */
  corrected: DraftContent | null;
  model: string | null;
  reviewedAt: string;
}

export interface DraftRevision {
  content: DraftContent;
  reason: RevisionReason;
  review: DraftReview | null;
  model: string | null;
  at: string;
}

export interface PublishRecord {
  channel: string;
  at: string;
  url: string | null;
}

/** A constructive angle proposed for a draft from a trend, and what the fact-check made of it. */
export interface DraftAngle {
  question: string;
  /** The one checkable sentence that would have to be true. */
  claim: string;
  query: string;
  kept: boolean;
  reason: string;
  verdict: string | null;
  confidence: number | null;
  domains: string[];
  /** Its supporting sources, as they are in the draft's `sources` (origin "angle"). */
  sourceUrls: string[];
}

/** The trend a draft's article was found through (backend DraftTrend). */
export interface DraftTrend {
  id: string;
  name: string;
  signal: string;
  signalName: string;
  traffic: number | null;
  startedAt: string | null;
  link: string | null;
  /** A TikTok video a person gave: provider, id, url, title, author. */
  video: { provider: string; id: string | null; url: string; title: string | null; author: string | null } | null;
  angles: DraftAngle[];
  /** Why no angle was looked for, or what went wrong looking. */
  angleNote: string | null;
}

export interface ArticleDraft {
  id: string;
  sourceArticleId: string;
  language: DraftLanguage;
  instructions: string;
  content: DraftContent;
  sources: DraftSource[];
  factChecks: DraftFactCheck[];
  metadata: DraftMetadata;
  review: DraftReview | null;
  revisions: DraftRevision[];
  status: DraftStatus;
  busy: DraftBusy | null;
  error: string | null;
  model: string | null;
  createdAt: string;
  updatedAt: string;
  published: PublishRecord[];
  /** Set when the analysed article came from a trending round. */
  trend?: DraftTrend | null;
}

export interface DraftSummary {
  id: string;
  sourceArticleId: string;
  language: DraftLanguage;
  title: string;
  status: DraftStatus;
  busy: DraftBusy | null;
  createdAt: string;
  updatedAt: string;
}

export const LANGUAGES: { code: DraftLanguage; label: string }[] = [
  { code: "ca", label: "Català" },
  { code: "es", label: "Español" },
  { code: "en", label: "English" },
];

/** What the page says while a background step runs. */
export const BUSY_LABEL: Record<DraftBusy, string> = {
  generating: "Writing the article…",
  reviewing: "Reviewing…",
  rewriting: "Rewriting…",
  publishing: "Publishing…",
};

/**
 * Every call to /api/drafts goes through here, so each stage's component
 * reports errors the same way. `path` is relative to /api/drafts, e.g.
 * `${id}/review`. Throws with the backend's `detail` (a 409's "busy"
 * included) or the proxy's `error`.
 */
export async function draftsApi<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const response = await fetch(`/api/drafts${path ? `/${path}` : ""}`, {
    method: init?.method ?? "GET",
    cache: "no-store",
    headers: init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : null;
    throw new Error(detail ?? data?.error ?? `Request failed (${response.status}).`);
  }

  return data as T;
}

/**
 * What every stage's component on /drafts/[id] receives. `onChange` takes
 * the draft the component's own API call returned; the page polls while
 * that draft is `busy`.
 */
export interface DraftStageProps {
  draft: ArticleDraft;
  onChange: (draft: ArticleDraft) => void;
}

// ----------------------------------------------------------------------
// The rewrite stage (docs/decisions/writing.md, "Rewriting"; backend
// src/api/rewrite_routes.py)
// ----------------------------------------------------------------------

/** The review's nine metrics, in the order a person reads them, with their labels. */
export const REVIEW_METRICS: { key: string; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "subtitle", label: "Subtitle" },
  { key: "grammar", label: "Grammar" },
  { key: "factConsistency", label: "Fact consistency" },
  { key: "coverageVerification", label: "Coverage verification" },
  { key: "seo", label: "SEO" },
  { key: "readability", label: "Readability" },
  { key: "hallucinationIndex", label: "Hallucination index" },
  { key: "style", label: "Writing style" },
];

/** GET /api/writing/targets: "the metrics expected", and what a rewrite may ask for. */
export interface RewriteTargetsInfo {
  /** The default minimum score (0-100) of each metric, under the metric's key. */
  targets: Record<string, number>;
  rounds: { default: number; max: number };
  maxInstructionsChars: number;
  /** The summary the review gives a metric it could not score. */
  unscoredSummary: string;
}

/** The body of POST /api/drafts/<id>/rewrite. Every field optional. */
export interface RewriteRequest {
  /** Overrides, under the metric keys: { factConsistency: 90 }. */
  targets?: Record<string, number>;
  /** Extra guidance for this rewrite, beside the draft's own instructions. */
  instructions?: string;
  maxRounds?: number;
}

/** A metric against its target. `unscored` counts neither for nor against. */
export type MetricStanding = "met" | "below" | "unscored";

// The backend's UNAVAILABLE_SUMMARY begins with this
// (src/services/corrector/text_corrector.py); used until the targets
// endpoint has given the exact text.
const UNSCORED_PREFIX = "Evaluation unavailable";

export function isUnscored(metric: CorrectionMetric, unscoredSummary?: string): boolean {
  return unscoredSummary ? metric.summary === unscoredSummary : metric.summary.startsWith(UNSCORED_PREFIX);
}

/** The backend's rule (rewriter.standings): a score at or above its target meets it. */
export function metricStanding(metric: CorrectionMetric, target: number, unscoredSummary?: string): MetricStanding {
  if (isUnscored(metric, unscoredSummary)) return "unscored";
  return metric.score >= target ? "met" : "below";
}
