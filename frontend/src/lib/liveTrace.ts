import { EvidenceStance, PhaseEvent, Verdict } from "@/lib/types";

/**
 * Folds a job's phase events into what a person watching wants to see:
 * per claim, what was searched, which sources came back, how each was
 * rated, and what the model concluded - filled in as the events arrive.
 *
 * Pure, and deliberately tolerant. The events come over the wire and out
 * of the job journal, so a field may be missing (an older run, a stage not
 * reached yet) and must leave a gap rather than throw: a viewer that
 * crashes on one odd event shows nothing for a run that is still going.
 *
 * Phase names are matched as string literals against the backend
 * (services/fact_checker/fact_checker.py and retrieval/evidence_retriever.py),
 * like PhaseStepper - a renamed phase silently empties the matching part.
 */

export type ClaimStep =
  | "searching"
  | "found"
  | "scraping"
  | "ranking"
  | "judging"
  | "done";

export interface TraceSource {
  url: string;
  title: string;
  domain: string | null;
  origin: "web" | "internal";
  engines: string[];
  snippet: string;
  publishedAt: string | null;
  /** The cheap similarity that decides which hits get scraped at all. */
  quickScore: number | null;
  relevanceScore: number | null;
  semanticScore: number | null;
  recencyScore: number | null;
  reliabilityScore: number | null;
  /** False: reliabilityScore is only the default for an unrated domain. */
  reliabilityKnown: boolean;
  stance: EvidenceStance | null;
  quote: string | null;
  cited: boolean | null;
  /** null until scraping has been attempted for this source. */
  scraped: boolean | null;
}

export interface TraceRejected {
  url: string;
  title: string;
  reason: string;
  score: number | null;
}

export interface ClaimTrace {
  claim: string;
  step: ClaimStep;
  queries: string[];
  webCount: number | null;
  internalCount: number | null;
  /** Every candidate the search returned, before any was cut. */
  found: TraceSource[];
  rejected: TraceRejected[];
  /** The sources that survived to be judged, with their ratings. */
  ranked: TraceSource[];
  cut: TraceRejected[];
  verdict: Verdict | null;
  confidence: number | null;
  explanation: string | null;
  agreements: string[];
  discrepancies: string[];
  independentDomains: number | null;
}

export interface JobTrace {
  title: string | null;
  validation: {
    passed: boolean;
    topicOk: boolean;
    positiveOk: boolean;
    duplicate: boolean;
    impactScore: number | null;
    impactReasons: string[];
  } | null;
  skippedReason: string | null;
  claimsSelected: number | null;
  claims: ClaimTrace[];
}

type Data = Record<string, unknown>;

const VERDICTS = new Set<string>([
  "TRUE",
  "PARTIALLY_TRUE",
  "FALSE",
  "MISLEADING",
  "UNVERIFIED",
]);

const asString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const asNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asBool = (value: unknown): boolean | null =>
  typeof value === "boolean" ? value : null;

const asList = (value: unknown): Data[] =>
  Array.isArray(value)
    ? value.filter((item): item is Data => typeof item === "object" && item !== null)
    : [];

const asStrings = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

function toSource(raw: Data): TraceSource {
  return {
    url: asString(raw.url) ?? "",
    title: asString(raw.title) ?? "",
    domain: asString(raw.domain) || null,
    origin: raw.origin === "internal" ? "internal" : "web",
    engines: asStrings(raw.engines),
    snippet: asString(raw.snippet) ?? "",
    publishedAt: asString(raw.publishedAt),
    quickScore: asNumber(raw.quickScore),
    relevanceScore: asNumber(raw.relevanceScore),
    semanticScore: asNumber(raw.semanticScore),
    recencyScore: asNumber(raw.recencyScore),
    reliabilityScore: asNumber(raw.reliabilityScore),
    reliabilityKnown: asBool(raw.reliabilityKnown) ?? false,
    stance:
      raw.stance === "supports" ||
      raw.stance === "contradicts" ||
      raw.stance === "unrelated"
        ? raw.stance
        : null,
    quote: asString(raw.quote),
    cited: asBool(raw.cited),
    scraped: null,
  };
}

const toRejected = (raw: Data): TraceRejected => ({
  url: asString(raw.url) ?? "",
  title: asString(raw.title) ?? "",
  reason: asString(raw.reason) ?? "",
  score: asNumber(raw.score),
});

function emptyClaim(claim: string): ClaimTrace {
  return {
    claim,
    step: "searching",
    queries: [],
    webCount: null,
    internalCount: null,
    found: [],
    rejected: [],
    ranked: [],
    cut: [],
    verdict: null,
    confidence: null,
    explanation: null,
    agreements: [],
    discrepancies: [],
    independentDomains: null,
  };
}

export function buildTrace(events: PhaseEvent[]): JobTrace {
  const trace: JobTrace = {
    title: null,
    validation: null,
    skippedReason: null,
    claimsSelected: null,
    claims: [],
  };

  const byClaim = new Map<string, ClaimTrace>();
  // url -> whether scraping produced text, per claim, applied to both the
  // candidate list and the ranked list since either may be drawn.
  const scraped = new Map<string, Map<string, boolean>>();

  function claimFor(data: Data): ClaimTrace | null {
    const text = asString(data.claim);
    if (!text) return null;

    let claim = byClaim.get(text);

    if (!claim) {
      claim = emptyClaim(text);
      byClaim.set(text, claim);
      trace.claims.push(claim);
    }

    return claim;
  }

  for (const event of events) {
    const data = event.data ?? {};

    switch (event.phase) {
      case "scraped":
      case "enriched":
        trace.title = asString(data.title) ?? trace.title;
        break;

      case "validated":
        trace.validation = {
          passed: data.passed === true,
          topicOk: data.topicOk === true,
          positiveOk: data.positiveOk === true,
          duplicate: data.duplicate === true,
          impactScore: asNumber(data.impactScore),
          impactReasons: asStrings(data.impactReasons),
        };
        break;

      case "skipped":
        trace.skippedReason = asString(data.reason);
        break;

      case "claims_selected":
        trace.claimsSelected = asNumber(data.count);
        break;

      case "retrieving_evidence": {
        claimFor(data);
        break;
      }

      case "searching_web": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.queries = asStrings(data.queries);
        claim.step = "searching";
        break;
      }

      case "web_results": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.queries = asStrings(data.queries).length
          ? asStrings(data.queries)
          : claim.queries;
        claim.webCount = asNumber(data.webCount);
        claim.internalCount = asNumber(data.internalCount);
        claim.found = asList(data.results).map(toSource);
        claim.step = "found";
        break;
      }

      case "scraping_sources": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.step = "scraping";
        break;
      }

      case "sources_scraped": {
        const claim = claimFor(data);
        if (!claim) break;
        const outcomes = new Map<string, boolean>();
        for (const source of asList(data.sources)) {
          const url = asString(source.url);
          if (url) outcomes.set(url, source.scraped === true);
        }
        scraped.set(claim.claim, outcomes);
        break;
      }

      case "evidence_retrieved": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.rejected = asList(data.rejectedSources).map(toRejected);
        if (asStrings(data.queries).length) claim.queries = asStrings(data.queries);
        claim.step = "ranking";
        break;
      }

      case "evidence_ranked": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.ranked = asList(data.sources).map(toSource);
        claim.cut = asList(data.cut).map(toRejected);
        claim.step = "ranking";
        break;
      }

      case "verifying_claim": {
        const claim = claimFor(data);
        if (claim) claim.step = "judging";
        break;
      }

      case "claim_checked": {
        const claim = claimFor(data);
        if (!claim) break;

        const verdict = asString(data.verdict);
        claim.verdict = VERDICTS.has(verdict ?? "") ? (verdict as Verdict) : null;
        claim.confidence = asNumber(data.confidence);
        claim.explanation = asString(data.explanation);
        claim.agreements = asStrings(data.agreements);
        claim.discrepancies = asStrings(data.discrepancies);
        claim.independentDomains = asNumber(data.independentDomains);

        const judged = asList(data.evidence).map(toSource);
        if (judged.length) claim.ranked = judged;

        claim.step = "done";
        break;
      }
    }
  }

  for (const claim of trace.claims) {
    const outcomes = scraped.get(claim.claim);
    if (!outcomes) continue;

    for (const source of [...claim.found, ...claim.ranked]) {
      const outcome = outcomes.get(source.url);
      if (outcome !== undefined) source.scraped = outcome;
    }
  }

  return trace;
}
