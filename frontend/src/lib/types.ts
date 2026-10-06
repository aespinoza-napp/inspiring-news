/** One of a topic's own keywords, scored against the article. */
export interface TopicKeyword {
  keyword: string;
  /** Cosine similarity to the whole article - only the order is meaningful. */
  score: number;
  /** Literal occurrences in the text; often 0 (the lists are English). */
  mentions: number;
}

export interface TopicPrediction {
  topic: string;
  confidence: number;
  probability: number;
  /** The topic's keywords, closest to the article first. */
  keywords?: TopicKeyword[];
}

export type Verdict =
  | "TRUE"
  /** Central assertion holds, but a source contradicts a detail of it. */
  | "PARTIALLY_TRUE"
  | "FALSE"
  | "MISLEADING"
  | "UNVERIFIED";

/** What one specific source says about a claim. */
export type EvidenceStance = "supports" | "contradicts" | "unrelated";

export type PipelineStage =
  | "admission_filter"
  | "claim_selection"
  | "evidence_retrieval"
  | "evidence_ranking"
  | "llm_verification"
  | "confidence_recalibration"
  | "aggregation";

export type EvidenceOrigin = "web" | "internal";

/**
 * Which question one of a claim's search queries asks. The anchor query
 * alone retrieves the claim's subject, which is how a claim mentioning
 * ACME came back with pages on the Greek etymology of the word.
 */
export type QueryKind = "anchor" | "proposition" | "refutation";

export interface RejectedSource {
  url: string;
  title: string;
  origin: EvidenceOrigin;
  stage: PipelineStage;
  reason: string;
  score: number | null;
}

export interface EvidenceItem {
  url: string;
  title: string;
  origin: EvidenceOrigin;
  relevanceScore: number | null;
  sourceReliability: number | null;
  publishedAt: string | null;
  cited: boolean;
  /** Registrable domain - two items sharing one are not independent. */
  domain?: string | null;
  /** Which SearXNG engines surfaced this result. */
  engines?: string[];
  /**
   * Which of the claim's queries returned this page. A hit only the
   * anchor query found is about the claim's subject; one the proposition
   * query found too is about what the claim actually asserts.
   */
  foundBy?: QueryKind[];
  /** Reciprocal-rank fusion score - how much those queries agreed. */
  fusionScore?: number | null;
  /**
   * The four factors behind relevanceScore. Retained so the UI can say
   * why one source outranked another instead of only that it did.
   */
  semanticScore?: number | null;
  /** How much of the claim's own vocabulary the source contains. */
  lexicalScore?: number | null;
  /**
   * Whether the source addresses the claim at all, as opposed to how
   * highly it ranks among those that do. Below the run's threshold a
   * source is cut before verification and appears under rejectedSources.
   */
  pertinenceScore?: number | null;
  recencyScore?: number | null;
  reliabilityScore?: number | null;
  /**
   * False when reliabilityScore is only the default for a domain nobody
   * has rated, not a rating - it should not be drawn like one.
   */
  reliabilityKnown?: boolean;
  stance?: EvidenceStance | null;
  /** Only set when the span was found verbatim in the source. */
  quote?: string | null;
}

export interface ClaimResult {
  text: string;
  confidence: number;
  verdict: Verdict | null;
  explanation: string | null;
  evidenceCount: number;
  evidence?: EvidenceItem[];
  rejectedSources?: RejectedSource[];
  reachedStage?: PipelineStage;
  stageNote?: string | null;
  rawVerdict?: Verdict | null;
  rawConfidence?: number | null;
  /** What the sources confirm, and where they diverge. */
  agreements?: string[];
  discrepancies?: string[];
  /** Distinct domains backing this claim, not raw evidence count. */
  independentDomains?: number;
}

export interface ValidityInfo {
  isValid: boolean;
  isDuplicate: boolean;
  hasTopic: boolean;
  reasons: string[];
  impactScore?: number;
  impactReasons?: string[];
  failedStage?: PipelineStage | null;
}

export interface SentimentScores {
  label: string;
  positive: number;
  neutral: number;
  negative: number;
  polarity: number;
  subjectivity: number;
  confidence: number;
  emotionalIntensity: number;
}

export interface QualityScores {
  readability: number;
  objectivity: number;
  constructiveness: number;
  inspirationalScore: number;
  hopefulness: number;
  societalImpact: number;
  novelty: number;
}

export interface FactCheckSummary {
  overallVerdict: Verdict;
  overallConfidence: number;
  claimsTotal: number;
  claimsChecked: number;
  /**
   * The article yielded fewer anchor claims than the run required, so
   * the verdict rests on less than it should. A caveat on the whole
   * report rather than on any single claim.
   */
  belowAnchorFloor?: boolean;
}

/**
 * Per-run threshold overrides. Send only the knobs you want to change -
 * anything omitted falls back to the backend's environment default
 * (settings.*). Field names mirror the backend's ThresholdOverrides;
 * out-of-range or unknown names come back as a 422.
 */
export interface ThresholdOverrides {
  topic_classifier_threshold?: number;
  entity_threshold?: number;
  claim_min_confidence?: number;
  opinion_max_score?: number;
  min_body_length?: number;
  topic_min_confidence?: number;
  positive_impact_min_score?: number;
  /** Whether low objectivity / strong negative sentiment reject outright. */
  positive_impact_hard_fail_enabled?: boolean;
  duplicate_threshold?: number;
  relatedness_threshold?: number;
  anchor_claims_min?: number;
  anchor_claims_max?: number;
  min_independent_domains?: number;
  claim_dedup_threshold?: number;
  evidence_fetch_candidates?: number;
  max_evidence_per_claim?: number;
  min_evidence_for_verdict?: number;
}

/** The fully-resolved set a run actually used: defaults + overrides. */
export type ResolvedThresholds = Required<ThresholdOverrides>;

/**
 * Where this run was written in the backend's three storage layers, and
 * whether the article cleared the editorial bar. `null` when the backend
 * has persistence switched off (settings.LAKE_ENABLED).
 */
export interface StorageInfo {
  /** True only when all three layers were written. */
  persisted: boolean;
  runId?: string;
  contentHash?: string;
  publishable?: boolean;
  /**
   * Record id per layer, or null for a layer whose write failed - the
   * layers are written independently as each stage completes, so one
   * failing does not stop the others.
   */
  records?: {
    raw: string | null;
    processed: string | null;
    exploitation: string | null;
  };
  error?: string;
}

export interface AnalysisResult {
  url: string;
  title?: string;
  error?: string;
  cached?: boolean;
  keywords?: string[];
  entities?: Record<string, string[]>;
  topics?: TopicPrediction[];
  sentiment?: SentimentScores;
  quality?: QualityScores;
  claims?: ClaimResult[];
  validity?: ValidityInfo;
  factCheck?: FactCheckSummary;
  storage?: StorageInfo | null;
  thresholds?: ResolvedThresholds;
}

export interface AnalyzeResponse {
  results: AnalysisResult[];
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface PhaseEvent {
  phase: string;
  data: Record<string, unknown>;
  at: string;
}

export interface AnalysisJob {
  jobId: string;
  /** For a claim check, the claim text itself. */
  url: string;
  /** "claim" for POST /verify-claim, otherwise a full article run. */
  kind?: "article" | "claim";
  status: JobStatus;
  events: PhaseEvent[];
  /** Total events, even when `events` was left out of a list response. */
  eventCount?: number;
  result: AnalysisResult | null;
  error: string | null;
  createdAt?: string;
  updatedAt?: string;
}

/** GET /analyze/jobs - what is running now and what ran recently. */
export interface LiveJobsResponse {
  jobs: AnalysisJob[];
}

/**
 * POST /analyze/jobs/batch - bulk form of POST /analyze/jobs. One entry
 * per input url, in input order; two urls that dedupe onto the same
 * backend job (identical url, or one already in flight) share a jobId.
 */
export interface BatchJobRef {
  url: string;
  jobId: string;
}

export interface CreateAnalysisJobsBatchResponse {
  jobs: BatchJobRef[];
}

/**
 * GET /analyze/jobs/batch?ids=... - one entry per requested job id.
 * "not_found" only happens after a backend restart (the in-memory job
 * store is single-process and does not survive one).
 */
export type BatchJobStatusEntry =
  | AnalysisJob
  | { jobId: string; status: "not_found" };

export interface AnalysisJobsBatchStatusResponse {
  jobs: BatchJobStatusEntry[];
}

export interface CorrectionMetric {
  score: number;
  summary: string;
  issues: string[];
}

export interface CorrectionReport {
  grammar: CorrectionMetric;
  factConsistency: CorrectionMetric;
  coverageVerification: CorrectionMetric;
  seo: CorrectionMetric;
  readability: CorrectionMetric;
  hallucinationIndex: CorrectionMetric;
  style: CorrectionMetric;
}


/**
 * POST /verify-claim - one claim checked on its own, with no article
 * around it. Runs the same verification stage the article pipeline uses,
 * so the verdict matches what a full run would produce for that claim.
 */
export interface ClaimEvidence {
  url: string;
  title: string;
  snippet?: string;
  origin: EvidenceOrigin;
  relevanceScore?: number | null;
  sourceReliability?: number | null;
  publishedAt?: string | null;
  cited: boolean;
}

export interface ClaimVerification {
  claim: string;
  entities: Record<string, string[]>;
  verdict: Verdict;
  confidence: number;
  explanation: string;
  evidenceCount: number;
  evidence: ClaimEvidence[];
  rejectedSources: RejectedSource[];
  reachedStage: PipelineStage;
  stageNote: string | null;
  /**
   * What the LLM said before the confidence scorer recalibrated it. It
   * differs from `verdict` exactly when the verdict was forced down -
   * no evidence retrieved, or a definitive answer citing nothing.
   */
  rawVerdict: Verdict | null;
  rawConfidence: number | null;
  thresholds: ResolvedThresholds;
}

/**
 * POST /enrich - the NLP stage on its own, over pasted text. Nothing is
 * fetched and nothing is stored.
 */
export interface EnrichedClaim {
  text: string;
  confidence: number;
  entities: Record<string, string[]>;
}

export interface EnrichmentResult {
  title: string;
  /** Detected from the body unless the request named one. */
  language: string | null;
  keywords: string[];
  entities: Record<string, string[]>;
  topics: TopicPrediction[];
  claims: EnrichedClaim[];
  sentiment: SentimentScores;
  quality: QualityScores;
  /**
   * The vector is 1024 floats - too big to be useful here, so the
   * backend sends its shape plus the first few values.
   */
  embedding: {
    model: string;
    dimension: number;
    preview: number[];
  };
  thresholds: ResolvedThresholds;
  extraction: ExtractionReport;
}

/**
 * Where one extracted field's value came from: typed in by the caller,
 * pulled from the fetched page, or absent from both.
 */
export type FieldOrigin = "supplied" | "extracted" | "missing";

export interface ExtractedField {
  value: string | null;
  origin: FieldOrigin;
}

/**
 * What `/enrich` started from. With a URL, the page is fetched with the
 * same extractor the article analyzer uses, so this is what a real run
 * would have had to work with.
 */
export interface ExtractionReport {
  url: string | null;
  fetched: boolean;
  /** Why the page could not be fetched, when a URL was given and it failed. */
  error: string | null;
  title: ExtractedField;
  author: ExtractedField;
  /** ISO date (YYYY-MM-DD). */
  publishedAt: ExtractedField;
  imageUrl: string | null;
  body: {
    origin: FieldOrigin;
    length: number;
    preview: string;
  };
}

/**
 * What one scraper request came to. Only `ok` produced an article; the
 * rest say which fix a failing source needs.
 */
export type ScrapeOutcome =
  | "ok"
  | "too_short"
  | "no_content"
  | "http_error"
  | "timeout"
  | "connection_error"
  | "blocked"
  | "error"
  | "unavailable";

/** GET /scraper/stats - one row per domain the scraper has fetched from. */
export interface ScraperDomainStats {
  domain: string;
  /** One per page wanted; outcomes and the success rate are per extraction. */
  extractions: number;
  /**
   * HTTP requests actually sent. Fewer than extractions when a fallback
   * parser read a page already fetched, or the guard refused the URL.
   */
  requests: number;
  ok: number;
  failed: number;
  /** ok / requests, 0-1; null before any request. */
  successRate: number | null;
  outcomes: Partial<Record<ScrapeOutcome, number>>;
  /** article | evidence | enrichment | ingestion | discovery | source_check | probe | labelling */
  purposes: Record<string, number>;
  /** Which strategy produced the article, for extractions that got one. */
  strategies: Record<string, number>;
  /** How often each strategy was tried at all. */
  tried: Record<string, number>;
  /** Configured source ids; "web" for a URL no source owns. */
  sources: string[];
  avgMs: number | null;
  lastAt: string | null;
  lastUrl: string | null;
  lastOutcome: ScrapeOutcome | null;
  lastStatus: number | null;
  /** The most recent failure, kept even after the domain recovers. */
  lastError: string | null;
  lastErrorAt: string | null;
}

export interface ScraperStats {
  since: string;
  totals: {
    domains: number;
    extractions: number;
    requests: number;
    ok: number;
    failed: number;
    outcomes: Partial<Record<ScrapeOutcome, number>>;
    strategies: Record<string, number>;
  };
  domains: ScraperDomainStats[];
}

/** GET /scraper/articles - articles stored in the lake, per domain. */
export interface ScrapedDomainStats {
  domain: string;
  /** Raw records: every stored fetch, re-analyses included. */
  scraped: number;
  /** Distinct articles by host and path. */
  uniqueUrls: number;
  uniqueContents: number;
  withTitle: number;
  withAuthor: number;
  withDate: number;
  avgLength: number | null;
  languages: Record<string, number>;
  processed: number;
  stored: number;
  publishable: number;
  rejected: number;
  /** YYYY-MM-DD */
  firstScraped: string | null;
  lastScraped: string | null;
}

export interface ScrapedArticles {
  totals: {
    domains: number;
    scraped: number;
    uniqueUrls: number;
    withTitle: number;
    withAuthor: number;
    withDate: number;
    processed: number;
    stored: number;
    publishable: number;
    rejected: number;
  };
  /** Days with at least one scrape, oldest first. */
  daily: { date: string; scraped: number }[];
  domains: ScrapedDomainStats[];
}

/** GET /ingest/sources */
export interface IngestSource {
  id: string;
  name: string;
  language: string;
  rssUrl: string | null;
  requiresJavascript: boolean;
  /** The topic groups this source is read for (its YAML's `groups`). */
  groups: string[];
}

/** One of the five topic groups (backend src/config/topics.py TOPIC_GROUPS). */
export interface TopicGroup {
  id: string;
  name: string;
  topics: { id: string; name: string }[];
  /** Enabled sources that cover it. */
  sources: number;
}

/** GET /ingest/sources */
export interface IngestSourcesResponse {
  sources: IngestSource[];
  groups: TopicGroup[];
  maxGroups: number;
  maxSelected: number;
  /** Candidates a round shows, best first, and the most it shows when asked for more. */
  listed: number;
  maxListed: number;
  lastRun: IngestReport | null;
}

/** What the embeddings said about a candidate (backend mission_screen.Reading), cosine similarities. */
export interface CandidateReading {
  nearestTopic: string;
  topic: number;
  nearestOff: string;
  off: number;
  /** Nearness to the description of positive impact. */
  impact: number;
}

/** A candidate's place in the ranking (backend src/services/selection/ranking.py). */
export interface CandidateRank {
  /** 0-1: news 60%, source record 25%, reliability 15% (the round's `ranking.weights`). */
  score: number;
  /** 0-1, from the story's own title and summary; null when nothing was read. */
  news: number | null;
  /** 0-1: the share of the source's newest items the mission screen kept this round, smoothed. */
  record: number;
  /** The source's configured reliability rating, as is. */
  reliability: number;
}

/** One article a round found, before anything about it is fetched. */
export interface Candidate {
  url: string;
  source: string;
  sourceName: string;
  language: string;
  groups: string[];
  /** The feed's title, or one made from the URL's slug (`titleFrom: "url"`). */
  title: string | null;
  titleFrom: "feed" | "url";
  summary: string | null;
  publishedAt: string | null;
  method: string | null;
  /** Absent on rounds made before the ranking (2026-10-06). */
  reading?: CandidateReading | null;
  rank?: CandidateRank;
  /** The same story as this url, ranked better: placed after every distinct story. */
  sameStoryAs?: string;
}

export interface CandidateSourceRow {
  source: string;
  name: string;
  language: string;
  method: string | null;
  discovered: number;
  alreadyStored: number;
  candidates: number;
  deferred: number;
  /** How many of its newest the mission screen ruled on (0 for a positive outlet); the source record's base. */
  judged?: number;
  /** Left out by the mission screen; absent on rounds before 2026-10-06. */
  screened?: number;
  /** Dropped as older than the discovery age limit. */
  stale?: number;
  error: string | null;
}

/** A candidate the mission screen left out, and why. */
export interface ScreenedCandidate {
  url: string;
  source: string;
  sourceName: string;
  title: string | null;
  /** politics, labour, crime, disaster, conflict, celebrity, sport, markets, service or obituary. */
  offMission: string;
  /** How much nearer that is than the nearest topic; null when the headline decided (obituary). */
  margin: number | null;
  nearestTopic: string | null;
}

export interface MissionScreenState {
  /** off: none configured; unavailable: inference/ unreachable, nothing left out. */
  status: "ok" | "off" | "unavailable";
  margin: number;
  /** Categories held to another margin (politics: 0). */
  margins?: Record<string, number>;
  error: string | null;
}

export interface ScoredCandidate {
  url: string;
  /** 0-10; null when the model left it out. */
  score: number | null;
  reason: string | null;
}

export interface AISelectionState {
  status: "running" | "done" | "failed";
  startedAt: string;
  finishedAt?: string;
  limit: number;
  minScore: number;
  picks?: ScoredCandidate[];
  scored?: ScoredCandidate[];
  model?: string;
  calls?: number;
  unusable?: number;
  elapsedMs?: number;
  notes?: string[];
  error?: string;
}

export interface QueuedSelection {
  at: string;
  urls: string[];
  jobs: { url: string; jobId: string | null; reused: boolean; error?: string }[];
  /** Worked out by the backend from the AI's proposal, not claimed by the page. */
  selectedBy: "user" | "ai" | "ai+user";
  aiProposed: number;
  aiKept: number;
  aiDropped: number;
  userAdded: number;
}

/** POST /ingest/rounds, GET /ingest/rounds/{id} */
export interface CandidateRound {
  id: string;
  startedAt: string;
  groups: string[];
  topics: string[];
  perSource: number;
  sources: CandidateSourceRow[];
  /** The ones shown and choosable, best first: 20, up to 40 when asked for more. */
  candidates: Candidate[];
  /** Ranked below those shown; POST .../more brings the next into view. */
  reserve?: Candidate[];
  /** Absent on rounds made before the ranking. `sameStory`: the similarity at which two candidates are one story. */
  ranking?: { weights: Record<string, number>; sameStory?: number };
  /** Absent on rounds made before the screen existed. */
  screen?: MissionScreenState;
  screened?: ScreenedCandidate[];
  totals: {
    sources: number;
    discovered: number;
    alreadyStored: number;
    candidates: number;
    deferred: number;
    screened?: number;
    stale?: number;
    failed: number;
    /** The same story again, ranked after every distinct one. */
    sameStory?: number;
  };
  aiSelection: AISelectionState | null;
  queued: QueuedSelection | null;
}

/** GET /ingest/rounds */
export interface CandidateRoundSummary {
  id: string;
  startedAt: string | null;
  groups: string[] | null;
  totals: CandidateRound["totals"] | null;
  aiStatus: AISelectionState["status"] | null;
  aiPicks: number;
  queued: number;
  selectedBy: QueuedSelection["selectedBy"] | null;
}

export interface IngestSourceRun {
  source: string;
  name: string;
  /** The discovery strategy that found the links; null when none did. */
  method: string | null;
  discovered: number;
  alreadyStored: number;
  queued: { url: string; jobId: string; reused: boolean }[];
  /** New articles beyond perSource, left for a later run. */
  deferred: number;
  error: string | null;
}

/** POST /ingest */
export interface IngestReport {
  startedAt: string;
  perSource: number;
  totals: {
    sources: number;
    discovered: number;
    alreadyStored: number;
    queued: number;
    deferred: number;
    failed: number;
  };
  sources: IngestSourceRun[];
}

/** GET /api/sources/check: every configured source YAML. */
export interface CheckableSource {
  id: string;
  name: string;
  language: string;
  enabled: boolean;
  rssUrl: string | null;
  requiresJavascript: boolean;
}

/** One sample article a source check tried to extract. */
export interface SourceCheckSample {
  url: string;
  outcome: ScrapeOutcome;
  /** The strategy that produced the article; null when none did. */
  strategy: string | null;
  tried: string[];
  status: number | null;
  error: string | null;
  elapsedMs: number;
  title: string | null;
  author: string | null;
  publishedAt: string | null;
  bodyLength: number;
  language: string | null;
  /** Of title / author / published_at, what an extracted article lacked. */
  missing: string[];
}

export type SourceVerdict = "ok" | "partial" | "broken";

export interface SourceCheckRow {
  source: string;
  name: string;
  language: string;
  enabled: boolean;
  requiresJavascript: boolean;
  baseUrl: string;
  rssUrl: string | null;
  verdict: SourceVerdict;
  discovery: {
    method: string | null;
    tried: string[];
    found: number;
    error: string | null;
  };
  samples: SourceCheckSample[];
  elapsedMs: number;
}

/** POST /api/sources/check */
export interface SourceCheckReport {
  startedAt: string;
  perSource: number;
  totals: { sources: number; ok: number; partial: number; broken: number };
  sources: SourceCheckRow[];
}

// ---------------------------------------------------------------------
// GET/POST /scraper/probe - is each source up, and can we read it?
// backend/src/services/scraper/source_probe.py
// ---------------------------------------------------------------------

export type ProbeStatus = "up" | "degraded" | "down";

export interface ProbeSection {
  url: string;
  advertised: boolean;
  status: number | null;
  outcome: string;
  error: string | null;
  links: number;
}

export interface ProbeSample {
  url: string;
  via: "feed" | "topic_page";
  ok: boolean;
  outcome: string;
  status: number | null;
  error: string | null;
  strategy: string | null;
  ms: number | null;
  title: boolean;
  author: boolean;
  date: boolean;
  chars: number;
}

export interface ProbeSource {
  source: string;
  name: string;
  language: string;
  status: ProbeStatus;
  reason: string;
  homepageStatus: number | null;
  homepageError: string | null;
  feedMethod: string | null;
  feedLinks: number;
  feedError: string | null;
  topicLinks: number;
  extraLinks: number;
  sections: ProbeSection[];
  sampled: number;
  extracted: number;
  sample: ProbeSample[];
  elapsedMs: number;
}

export interface SearchHealth {
  language: string;
  query: string;
  ok: boolean;
  results?: number;
  engines?: string[];
  unresponsive?: { engine: string; reason: string }[];
  error: string | null;
  ms?: number;
}

export interface ProbeReport {
  startedAt: string;
  finishedAt: string;
  perSource: number;
  totals: {
    sources: number;
    up: number;
    degraded: number;
    down: number;
    feedLinks: number;
    topicLinks: number;
    extraLinks: number;
    sampled: number;
    extracted: number;
  };
  sources: ProbeSource[];
  search: SearchHealth[];
}

export interface ProbeState {
  running: boolean;
  startedAt: string | null;
  error: string | null;
  report: ProbeReport | null;
}

// ---------------------------------------------------------------------
// Graph (/graph page) - mirrors backend/src/services/graph/ and the
// /graph/* endpoints in backend/src/api/routes.py.
// ---------------------------------------------------------------------

export type GraphMethod = "pipeline" | "manual";

export interface GraphNodeDecl {
  label: string;
  key: string;
  description: string;
  properties: string[];
}

export interface GraphRelationshipDecl {
  type: string;
  from: string;
  to: string;
  description: string;
  properties: string[];
}

export interface GraphPatternCount {
  from: string | null;
  type: string;
  to: string | null;
  count: number;
}

export interface GraphSchema {
  nodes: GraphNodeDecl[];
  relationships: GraphRelationshipDecl[];
  /** GLiNER entity type -> the second label an Entity node carries. */
  entityTypes: Record<string, string>;
  methods: GraphMethod[];
  live: {
    labels: Record<string, number>;
    patterns: GraphPatternCount[];
    methods: { type: string; method: GraphMethod; count: number }[];
  };
}

export interface GraphNode {
  kind: "node";
  /** Neo4j element id: stable within one query, not across restarts. */
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface GraphRelationship {
  kind: "relationship";
  id: string;
  type: string;
  start: string;
  end: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

export interface GraphQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  graph: GraphData;
  truncated: boolean;
  maxRows: number;
  elapsedMs: number;
  notices: string[];
}

export interface GraphPreset {
  id: string;
  title: string;
  description: string;
  view: "graph" | "table";
  cypher: string;
  params?: { name: string; label: string }[];
}

export interface GraphArticle {
  url: string;
  title: string | null;
  source: string | null;
  language: string | null;
  verdict: string | null;
  analyzedAt: string | null;
  labelled: boolean;
  claims: number;
  entities: number;
}

export interface RelatedArticle {
  url: string;
  title: string | null;
  source: string | null;
  verdict: string | null;
  score: number;
  shared: { kind: "claim" | "evidence" | "entity" | "topic"; via: string; weight: number }[];
}

export interface RelatedArticles {
  url: string;
  found: boolean;
  title: string | null;
  related: RelatedArticle[];
}

export interface GraphSyncReport {
  sources: number;
  facts: number;
  articles: number;
  errors: { item: string; error: string }[];
}

// GET /scraper/freshness (backend src/services/freshness.py): how long
// articles take to reach us after they are published.

export type FreshnessLag = "seen" | "queue" | "reception" | "processing" | "available";

export interface FreshnessStat {
  n: number;
  median: number | null;
  p90: number | null;
  /** Published after we fetched it: a wrong timezone or a rewritten feed time. Kept out of the median. */
  negative: number;
}

export interface FreshnessSummary {
  articles: number;
  ingested: number;
  publishable: number;
  publishedFrom: { feed: number; page: number; date: number; none: number };
  noTimezone: number;
  /** Lags in hours, between precise times only. */
  hours: Record<FreshnessLag, FreshnessStat>;
  /** Fetched date minus published date, for articles that state only a date. */
  receptionDays: FreshnessStat;
}

export interface FreshnessArticle {
  key: string;
  url: string;
  sourceId: string | null;
  domain: string;
  title: string | null;
  via: "ingestion" | "posted";
  publishedAt: string | null;
  publishedFrom: "feed" | "page" | "date" | null;
  noTimezone: boolean;
  firstSeenAt: string | null;
  fetchedAt: string | null;
  analysedAt: string | null;
  availableAt: string | null;
  publishable: boolean;
  lagHours: Record<FreshnessLag, number | null>;
  receptionDays: number | null;
}

export interface Freshness {
  totals: FreshnessSummary;
  sources: (FreshnessSummary & { source: string })[];
  articles: FreshnessArticle[];
  sightings: number;
}
