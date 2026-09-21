import { EvidenceStance, PhaseEvent, QueryKind, Verdict } from "@/lib/types";

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
 *
 * The backend checks an article's claims **concurrently**, so their
 * events interleave: one claim can be judged while another is still
 * searching. Two things keep that legible rather than jumpy.
 *
 * First, the row order is fixed by `claims_selected`, which arrives
 * before any claim has been checked and carries the whole set. Creating
 * rows from whichever event happened to arrive first would reorder the
 * list as the run progressed.
 *
 * Second, every per-claim event carries a `claimIndex`. Matching on
 * claim text still works and is kept as the fallback for journalled runs
 * from before the index existed, but the index is what a claim is when
 * the server already knows.
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
  /** Which of the claim's queries returned this page. */
  foundBy: QueryKind[];
  /** How much those queries agreed it was worth returning. */
  fusionScore: number | null;
  snippet: string;
  publishedAt: string | null;
  /** The cheap similarity that decides which hits get scraped at all. */
  quickScore: number | null;
  relevanceScore: number | null;
  semanticScore: number | null;
  /** How much of the claim's own vocabulary this source contains. */
  lexicalScore: number | null;
  /** Whether it addresses the claim at all, not how highly it ranks. */
  pertinenceScore: number | null;
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
  /** Position in the selected set - what the backend calls this claim. */
  index: number;
  step: ClaimStep;
  queries: string[];
  /** Which question each of `queries` asks, index for index. */
  queryKinds: QueryKind[];
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

const QUERY_KINDS = new Set<string>(["anchor", "proposition", "refutation"]);

const isQueryKind = (value: string): value is QueryKind =>
  QUERY_KINDS.has(value);

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
    foundBy: asStrings(raw.foundBy).filter(isQueryKind),
    fusionScore: asNumber(raw.fusionScore),
    snippet: asString(raw.snippet) ?? "",
    publishedAt: asString(raw.publishedAt),
    quickScore: asNumber(raw.quickScore),
    relevanceScore: asNumber(raw.relevanceScore),
    semanticScore: asNumber(raw.semanticScore),
    lexicalScore: asNumber(raw.lexicalScore),
    pertinenceScore: asNumber(raw.pertinenceScore),
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

function emptyClaim(claim: string, index: number): ClaimTrace {
  return {
    claim,
    index,
    step: "searching",
    queries: [],
    queryKinds: [],
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
  const byIndex = new Map<number, ClaimTrace>();
  // url -> whether scraping produced text, per claim, applied to both the
  // candidate list and the ranked list since either may be drawn.
  const scraped = new Map<string, Map<string, boolean>>();

  function addClaim(text: string, index: number): ClaimTrace {
    const claim = emptyClaim(text, index);
    byClaim.set(text, claim);
    byIndex.set(index, claim);
    trace.claims.push(claim);
    return claim;
  }

  function claimFor(data: Data): ClaimTrace | null {
    const index = asNumber(data.claimIndex);

    // The index is what the backend calls this claim, and it is on every
    // per-claim event. Text is the fallback: events replayed out of the
    // journal may predate the index, and dropping those would empty the
    // view for exactly the runs someone is looking back at.
    if (index !== null) {
      const known = byIndex.get(index);
      if (known) return known;
    }

    const text = asString(data.claim);
    if (!text) return null;

    const known = byClaim.get(text);
    if (known) return known;

    // An event for a claim `claims_selected` did not announce. Appended
    // rather than dropped - a viewer showing nothing is worse than one
    // showing a row in an unexpected place.
    return addClaim(text, index ?? trace.claims.length);
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

      case "claims_selected": {
        trace.claimsSelected = asNumber(data.count);

        // Every selected claim, in the order the backend chose them,
        // before any has been checked. With the checks running
        // concurrently there is no order in which their events arrive,
        // so rows created from the first event to turn up would
        // reshuffle themselves as the run went on.
        for (const entry of asList(data.claims)) {
          const text = asString(entry.text);
          if (!text || byClaim.has(text)) continue;
          addClaim(text, asNumber(entry.index) ?? trace.claims.length);
        }
        break;
      }

      case "retrieving_evidence": {
        claimFor(data);
        break;
      }

      case "searching_web": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.queries = asStrings(data.queries);
        claim.queryKinds = asStrings(data.queryKinds).filter(isQueryKind);
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
