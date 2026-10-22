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

/** One search query: how long it took and how it was answered. */
export interface QueryTiming {
  kind: QueryKind | null;
  query: string;
  seconds: number | null;
  /** Results it returned; null when it failed. */
  results: number | null;
  /** cache, shared (another claim's request), searxng, duckduckgo, failed. */
  via: string | null;
  error: string | null;
}

/** One evidence page: how long it took and what it gave. */
export interface PageTiming {
  url: string;
  seconds: number | null;
  /** page (its text), snippet (would not open), cached, late (deadline). */
  outcome: string | null;
}

/**
 * Where one claim's seconds went. Each field is null until its stage has
 * reported, and stays null for a run from before the backend measured it
 * (2026-10-22) - except `total`, which the event timestamps give anyway.
 */
export interface ClaimTiming {
  queries: QueryTiming[];
  /** The whole web search, every query (they run concurrently). */
  search: number | null;
  /** Embedding the claim, the stored-article search and the pre-rank. */
  claimEmbedding: number | null;
  internal: number | null;
  prerank: number | null;
  pages: PageTiming[];
  /** Waiting for the pages, wall clock. */
  fetch: number | null;
  /** How long the pages were waited for at most (the claim's deadline). */
  fetchWait: number | null;
  ranking: number | null;
  /** Queued behind another claim's call to the one model. */
  llmWait: number | null;
  /** The model reading the prompt and writing its answer. */
  llm: number | null;
  model: string | null;
  promptTokens: number | null;
  completionTokens: number | null;
  /** The claim, search to verdict. */
  total: number | null;
  deadline: number | null;
  deadlineExceeded: boolean;
}

/** Where an article's seconds went, stage by stage, from event times. */
export interface JobTiming {
  stages: { id: string; label: string; seconds: number }[];
  total: number | null;
  /** The run is still going: the last stage is open-ended. */
  running: boolean;
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
  timing: ClaimTiming;
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
  timing: JobTiming;
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
      raw.stance === "unrelated" ||
      raw.stance === "silent"
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
    timing: emptyTiming(),
  };
}

function emptyTiming(): ClaimTiming {
  return {
    queries: [],
    search: null,
    claimEmbedding: null,
    internal: null,
    prerank: null,
    pages: [],
    fetch: null,
    fetchWait: null,
    ranking: null,
    llmWait: null,
    llm: null,
    model: null,
    promptTokens: null,
    completionTokens: null,
    total: null,
    deadline: null,
    deadlineExceeded: false,
  };
}

const asRecord = (value: unknown): Data =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Data) : {};

/** An event's time in ms, or null when it has none the browser can read. */
const timeOf = (event: PhaseEvent): number | null => {
  const ms = Date.parse(event.at);
  return Number.isFinite(ms) ? ms : null;
};

const secondsBetween = (from: number | null, to: number | null): number | null =>
  from !== null && to !== null && to >= from ? (to - from) / 1000 : null;

// An article's stages, each ended by the first event of that name. Phase
// names are the backend's literals, like PhaseStepper's; a stage whose
// closing event never came is left out rather than guessed.
const JOB_STAGES: { id: string; label: string; ends: string[] }[] = [
  { id: "fetch", label: "Fetch", ends: ["scraped"] },
  { id: "enrich", label: "Enrich", ends: ["enriched"] },
  { id: "admission", label: "Admission", ends: ["validated"] },
  { id: "selection", label: "Claim selection", ends: ["claims_selected"] },
  { id: "factcheck", label: "Fact-check", ends: ["fact_check_done"] },
  { id: "store", label: "Store", ends: ["stored", "store_failed"] },
];

function jobTiming(events: PhaseEvent[]): JobTiming {
  const times = events.map(timeOf);
  const first = times.find((time): time is number => time !== null) ?? null;

  const firstAt = new Map<string, number>();
  events.forEach((event, index) => {
    const time = times[index];
    if (time !== null && !firstAt.has(event.phase)) firstAt.set(event.phase, time);
  });

  const stages: JobTiming["stages"] = [];
  let previous = first;

  for (const stage of JOB_STAGES) {
    const end = stage.ends.map((phase) => firstAt.get(phase)).find((time) => time !== undefined);
    if (end === undefined) continue;
    const seconds = secondsBetween(previous, end);
    if (seconds !== null) stages.push({ id: stage.id, label: stage.label, seconds });
    previous = end;
  }

  const last = [...times].reverse().find((time): time is number => time !== null) ?? null;
  const finished = firstAt.has("stored") || firstAt.has("store_failed") || firstAt.has("skipped");

  return { stages, total: secondsBetween(first, last), running: !finished };
}

export function buildTrace(events: PhaseEvent[]): JobTrace {
  const trace: JobTrace = {
    title: null,
    validation: null,
    skippedReason: null,
    claimsSelected: null,
    claims: [],
    timing: jobTiming(events),
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

  // When each claim started, from the events' own times: the claim's
  // total even for a run from before the backend measured its stages.
  const startedAt = new Map<ClaimTrace, number>();

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
        const claim = claimFor(data);
        const time = timeOf(event);
        if (claim && time !== null && !startedAt.has(claim)) startedAt.set(claim, time);
        if (claim) claim.timing.deadline = asNumber(data.deadline) ?? claim.timing.deadline;
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

        const timings = asRecord(data.timings);
        claim.timing.search = asNumber(timings.search);
        claim.timing.claimEmbedding = asNumber(timings.claimEmbedding);
        claim.timing.internal = asNumber(timings.internal);
        claim.timing.prerank = asNumber(timings.prerank);
        claim.timing.queries = asList(data.queryTimings).map((raw) => {
          const kind = asString(raw.kind);
          return {
            kind: kind && isQueryKind(kind) ? kind : null,
            query: asString(raw.query) ?? "",
            seconds: asNumber(raw.seconds),
            results: asNumber(raw.results),
            via: asString(raw.via),
            error: asString(raw.error),
          };
        });
        break;
      }

      case "scraping_sources": {
        const claim = claimFor(data);
        if (!claim) break;
        claim.step = "scraping";
        claim.timing.fetchWait = asNumber(data.wait);
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
        claim.timing.fetch = asNumber(data.seconds);
        claim.timing.pages = asList(data.sources).map((source) => ({
          url: asString(source.url) ?? "",
          seconds: asNumber(source.seconds),
          outcome: asString(source.outcome),
        }));
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
        claim.timing.ranking = asNumber(data.seconds);
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

        const timings = asRecord(data.timings);
        const llm = asRecord(data.llm);
        const deadline = asRecord(data.deadline);
        claim.timing.llmWait = asNumber(timings.llmWait);
        claim.timing.llm = asNumber(timings.llm);
        claim.timing.ranking = asNumber(timings.ranking) ?? claim.timing.ranking;
        claim.timing.model = asString(llm.model);
        claim.timing.promptTokens = asNumber(llm.promptTokens);
        claim.timing.completionTokens = asNumber(llm.completionTokens);
        claim.timing.deadline = asNumber(deadline.seconds) ?? claim.timing.deadline;
        claim.timing.deadlineExceeded = deadline.exceeded === true;
        // The backend's own clock when it sent one; else the events' times.
        claim.timing.total =
          asNumber(timings.total) ?? secondsBetween(startedAt.get(claim) ?? null, timeOf(event));
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
