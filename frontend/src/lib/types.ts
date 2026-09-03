export interface TopicPrediction {
  topic: string;
  confidence: number;
  probability: number;
}

export type Verdict = "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED";

export interface ClaimResult {
  text: string;
  confidence: number;
  verdict: Verdict | null;
  explanation: string | null;
  evidenceCount: number;
}

export interface ValidityInfo {
  isValid: boolean;
  isDuplicate: boolean;
  hasTopic: boolean;
  reasons: string[];
  impactScore?: number;
  impactReasons?: string[];
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
