// The writing flow's shapes (docs/decisions/writing.md). Mirrors
// backend/src/models/writer/draft.py exactly - keep the two in step, as
// lib/types.ts is kept with the analysis responses.

import { CorrectionMetric } from "@/lib/types";

export type DraftLanguage = "ca" | "es" | "en";

export type DraftStatus = "draft" | "approved" | "published";

export type DraftBusy = "generating" | "reviewing" | "rewriting" | "publishing";

export type RevisionReason = "generated" | "edited" | "corrected" | "rewritten";

export type SourceOrigin = "analysed" | "related" | "evidence";

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
