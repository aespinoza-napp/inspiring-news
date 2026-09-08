export interface TopicPrediction {
  topic: string;
  confidence: number;
  probability: number;
}

export type Verdict = "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED";

export type PipelineStage =
  | "admission_filter"
  | "claim_selection"
  | "evidence_retrieval"
  | "evidence_ranking"
  | "llm_verification"
  | "confidence_recalibration"
  | "aggregation";

export type EvidenceOrigin = "web" | "internal";

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
  min_body_length?: number;
  topic_min_confidence?: number;
  positive_impact_min_score?: number;
  duplicate_threshold?: number;
  relatedness_threshold?: number;
  max_claims_per_article?: number;
  claim_dedup_threshold?: number;
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
  url: string;
  status: JobStatus;
  events: PhaseEvent[];
  result: AnalysisResult | null;
  error: string | null;
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
}
