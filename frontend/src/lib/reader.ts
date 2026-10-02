/**
 * The reader view: the shapes `GET /reader/articles` and
 * `GET /reader/articles/{id}` return (backend/src/services/reader/views.py),
 * and the few pure helpers both reader pages share.
 *
 * Kept apart from lib/types.ts, which mirrors the operator endpoints:
 * this is a different audience over the same lake, and its shapes change
 * for different reasons. Keep it in sync with views.py all the same.
 */

import { EvidenceStance, QueryKind, Verdict } from "@/lib/types";

/**
 * How a claim's check ended. The backend derives it once so the pages
 * phrase it rather than re-deriving it from four fields.
 *
 * - judged: the model weighed real sources and gave a verdict.
 * - ungrounded: it answered, but could not point to a source that bears
 *   it out, so the guardrail made it UNVERIFIED (its answer is kept).
 * - no_evidence: searched, and nothing addressing the claim came back.
 *   A real UNVERIFIED: looked for and not found.
 * - search_unavailable / llm_unreachable / no_answer: failures of ours,
 *   not findings about the claim. Never shown as a verdict.
 */
export type ClaimOutcome =
  | "judged"
  | "ungrounded"
  | "no_evidence"
  | "search_unavailable"
  | "llm_unreachable"
  | "no_answer";

export const NOT_JUDGED: ClaimOutcome[] = ["search_unavailable", "llm_unreachable", "no_answer"];

/** The article's headline verdict: NOT_CHECKED when no claim was judged at all. */
export type DisplayVerdict = Verdict | "NOT_CHECKED";

export interface ReaderVerdictSummary {
  /** What the pipeline decided: worst claim wins. */
  overall: Verdict;
  display: DisplayVerdict;
  /** The pipeline's overall_confidence - an average across the claims' verdicts. */
  confidence: number | null;
  claimsTotal: number;
  claimsChecked: number;
  /** Only claims that were actually judged, by verdict. */
  counts: Partial<Record<Verdict, number>>;
  /** Claims whose check failed on our side, counted apart from the verdicts. */
  notJudged: number;
  searchUnavailable: number;
  llmUnreachable: number;
  noAnswer: number;
  sourcesCited: number;
  /** Fewer anchor claims than an article is meant to be judged by. */
  belowAnchorFloor: boolean;
}

export interface ReaderSourceName {
  id: string | null;
  name: string;
  domain: string;
}

export interface ReaderCard {
  /** Host and path, hashed: stable across re-analyses of the same article. */
  id: string;
  url: string;
  headline: string;
  /** False when `headline` is a stand-in (the URL slug, the lead, the domain). */
  titleExtracted: boolean;
  source: ReaderSourceName;
  language: string | null;
  topic: string | null;
  publishedAt: string | null;
  checkedAt: string | null;
  excerpt: string;
  verdict: ReaderVerdictSummary;
}

export interface ReaderFeed {
  total: number;
  offset: number;
  limit: number;
  items: ReaderCard[];
  /** Counted under the language filter, so a chip says what clicking it shows. */
  topics: { topic: string; count: number }[];
  /** Counted under the topic filter. */
  languages: { language: string; count: number }[];
  /** Why a feed can be empty: nothing analysed, or nothing that passed. */
  lake: { analysed: number; publishable: number };
}

export interface ReaderScores {
  /** What the ranker combined the four below into. */
  relevance: number | null;
  /** How well the page addresses the claim; below the run's floor it is cut. */
  pertinence: number | null;
  semantic: number | null;
  lexical: number | null;
  recency: number | null;
  reliability: number | null;
}

export interface ReaderSource {
  url: string;
  title: string;
  domain: string;
  origin: "web" | "internal";
  publishedAt: string | null;
  snippet: string;
  /** Whether the model relied on it - resolved by index before any reordering. */
  cited: boolean;
  stance: EvidenceStance | null;
  quote: string | null;
  /** False: `scores.reliability` is the default every unrated domain gets. */
  reliabilityKnown: boolean;
  foundBy: QueryKind[];
  scores: ReaderScores;
}

export interface ReaderNotUsed {
  url: string;
  title: string;
  stage: string | null;
  reason: string;
}

export interface ReaderClaim {
  index: number;
  text: string;
  verdict: Verdict;
  confidence: number | null;
  outcome: ClaimOutcome;
  explanation: string;
  /** What the model itself said, when the guardrails changed it. */
  modelVerdict: Verdict | null;
  note: string | null;
  /** Set even when other evidence exists: then it rests on stored articles only. */
  searchUnavailable: boolean;
  independentDomains: number;
  agreements: string[];
  discrepancies: string[];
  sources: ReaderSource[];
  notUsed: ReaderNotUsed[];
  notUsedTotal: number;
}

export interface ReaderArticle extends ReaderCard {
  author: string | null;
  summary: string;
  topics: { topic: string | null; confidence: number | null }[];
  keywords: string[];
  /** False when the record holding the claims could not be read. */
  claimsAvailable: boolean;
  claims: ReaderClaim[];
  uncheckedClaims: string[];
  uncheckedTotal: number;
  checkedWith: { model: string | null; pipelineVersion: string | null };
}

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

/** Worst first, the order the article verdict is decided in. */
export const VERDICT_ORDER: Verdict[] = ["FALSE", "MISLEADING", "UNVERIFIED", "PARTIALLY_TRUE", "TRUE"];

export const VERDICT_WORDS: Record<Verdict, string> = {
  TRUE: "true",
  PARTIALLY_TRUE: "partly true",
  FALSE: "false",
  MISLEADING: "misleading",
  UNVERIFIED: "unverified",
};

const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  es: "Spanish",
};

export function languageName(code: string | null): string {
  if (!code) return "Unknown language";
  return LANGUAGE_NAMES[code.toLowerCase()] ?? code.toUpperCase();
}

export function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : `${Math.round(value * 100)}%`;
}

/** A date for a reader: "18 Sep 2026". The raw string if it does not parse. */
export function readableDate(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** The badge's verdict; null renders VerdictBadge's "Not checked". */
export function badgeVerdict(summary: ReaderVerdictSummary): Verdict | null {
  return summary.display === "NOT_CHECKED" ? null : summary.display;
}

/** "2 true, 1 unverified" - judged claims only, worst first. */
export function tally(summary: ReaderVerdictSummary): string {
  return VERDICT_ORDER.filter((verdict) => summary.counts[verdict])
    .map((verdict) => `${summary.counts[verdict]} ${VERDICT_WORDS[verdict]}`)
    .join(", ");
}

/** Why claims went unjudged, e.g. "web search failed for 2, the model was unreachable for 1". */
export function notJudgedReasons(summary: ReaderVerdictSummary): string {
  return [
    summary.searchUnavailable && `web search failed for ${summary.searchUnavailable}`,
    summary.llmUnreachable && `the model was unreachable for ${summary.llmUnreachable}`,
    summary.noAnswer && `the model was unavailable or gave no usable answer for ${summary.noAnswer}`,
  ]
    .filter(Boolean)
    .join(", ");
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}
