/**
 * The shape of GET /evaluation/summary (backend/src/services/
 * evaluation_summary.py), kept beside the page that reads it rather than
 * in types.ts: nothing else uses it. Keep the two in sync.
 */

import { Verdict } from "@/lib/types";

export type TopicGroup = "society" | "science" | "environment" | "culture" | "health";

export type Annotator = "human" | "ai";

export interface EvaluationFact {
  id: string;
  claim: string | null;
  label: Verdict | string | null;
  labelRaw: string | null;
  language: string | null;
  site: string | null;
  claimant: string | null;
  claimDate: string | null;
  topic: string | null;
  group: TopicGroup | null;
  claimType: string | null;
  sourceTier: string | null;
  onlyOwnSource: boolean;
  evidenceDate: string | null;
  articleUrl: string | null;
  evidenceLinks: string[];
  note: string | null;
  createdAt: string | null;
  annotator: Annotator;
  reviewed: boolean;
}

export interface EvaluationTotals {
  total: number;
  target: number;
  minimum: number;
  perCell: number;
  byLabel: Record<string, number>;
  byGroup: Record<string, number>;
  byLanguage: Record<string, number>;
  byClaimType: Record<string, number>;
  bySourceTier: Record<string, number>;
  byAnnotator: Record<string, number>;
  reviewed: number;
  /** label -> group -> count */
  matrix: Record<string, Record<string, number>>;
  perDay: { date: string; value: number }[];
}

export interface SelectionBatch {
  file: string;
  date: string;
  articles: number;
  proposed: number;
  labelled: number;
  skipped: number;
  pending: number;
  byReason: Record<string, number>;
}

export interface SelectionSummary {
  batches: SelectionBatch[];
  broken: { file: string; error: string }[];
  proposed: number;
  labelled: number;
  skipped: number;
  pending: number;
  precision: number | null;
  byReason: Record<string, number>;
  byLanguage: Record<
    string,
    { labelled: number; skipped: number; pending: number; precision: number | null }
  >;
}

export interface HarnessRun {
  dataset: string;
  model: string;
  key: string;
  modifiedAt: number;
  /** metrics.json as the harness wrote it - read with the helpers below. */
  metrics: Record<string, unknown> | null;
  run: Record<string, unknown> | null;
  error: string | null;
}

export interface EvaluationSummary {
  facts: EvaluationFact[];
  brokenFacts: { file: string; error: string }[];
  totals: EvaluationTotals;
  selection: SelectionSummary;
  runs: HarnessRun[];
  labels: Verdict[];
  groups: Record<TopicGroup, string[]>;
  skipReasons: string[];
  found: boolean;
}

export const LABEL_NAMES: Record<string, string> = {
  TRUE: "True",
  PARTIALLY_TRUE: "Partly true",
  MISLEADING: "Misleading",
  FALSE: "False",
  UNVERIFIED: "Unverified",
};

export const GROUP_NAMES: Record<string, string> = {
  society: "Society",
  science: "Science",
  environment: "Environment",
  culture: "Culture",
  health: "Health",
};

export const SKIP_REASON_NAMES: Record<string, string> = {
  opinion: "Opinion",
  prediction: "Prediction or plan",
  trivial: "Trivial",
  fragment: "Fragment",
  duplicate: "Duplicate",
  other: "Other",
};

export const TIER_NAMES: Record<string, string> = {
  primary: "Primary",
  reference_media: "Reference media",
  press_release: "Press release",
  social_media: "Social media",
};

export function percent(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined || Number.isNaN(value)
    ? "–"
    : `${(value * 100).toFixed(digits)}%`;
}

export function isVerdict(value: unknown): value is Verdict {
  return typeof value === "string" && value in LABEL_NAMES;
}

// ---------------------------------------------------------------------
// Reading a harness report
//
// metrics.json is passed through as the harness wrote it, so the page
// reads it defensively: a key it does not know is skipped, never a crash.
// ---------------------------------------------------------------------

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** The first of several paths into a nested object that holds a value. */
export function pick(source: unknown, ...paths: string[]): unknown {
  for (const path of paths) {
    let node: unknown = source;
    for (const part of path.split(".")) {
      const record = asRecord(node);
      node = record ? record[part] : undefined;
    }
    if (node !== undefined && node !== null) return node;
  }
  return undefined;
}

/** A point estimate with an optional [low, high] interval. */
export interface Estimate {
  value: number;
  low: number | null;
  high: number | null;
}
