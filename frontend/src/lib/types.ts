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

export interface ClaimResult {
  text: string;
  confidence: number;
  verdict: Verdict | null;
  explanation: string | null;
  evidenceCount: number;
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
