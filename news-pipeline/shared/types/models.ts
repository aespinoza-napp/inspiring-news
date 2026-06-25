// ─── Core Domain Models ───────────────────────────────────────────────────────

export type ArticleStatus =
  | "raw"
  | "validated"
  | "enriched"
  | "transformed"
  | "media_selected"
  | "qa_passed"
  | "published"
  | "rejected";

export type SourceStatus = "active" | "inactive" | "under_review";

export type MediaAssetType = "image" | "video" | "audio" | "infographic";

export type PublicationStatus = "scheduled" | "published" | "failed" | "retracted";

export type PublicationChannel = "web" | "rss" | "social" | "newsletter" | "api";

// ─── NewsArticle ──────────────────────────────────────────────────────────────

export interface NewsArticle {
  id: string;
  title: string;
  content: string;
  source: Source;
  author: string;
  publication_date: string;       // ISO 8601
  language: string;               // BCP 47 e.g. "en", "es"
  category: string;
  sentiment_score: number | null; // -1.0 → 1.0  (set by NLP service)
  credibility_score: number | null; // 0.0 → 1.0 (set by fact-check service)
  keywords: string[];
  entities: Entity[];
  summary: string | null;
  images: MediaAsset[];
  status: ArticleStatus;
  created_at: string;
  updated_at: string;
}

export interface Entity {
  text: string;
  type: "PERSON" | "ORG" | "LOCATION" | "EVENT" | "OTHER";
  confidence: number;
}

// ─── Source ───────────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  name: string;
  url: string;
  category: string;
  reputation_score: number;  // 0.0 → 1.0
  bias_score: number;        // -1.0 (left) → 1.0 (right)
  status: SourceStatus;
  last_checked: string;      // ISO 8601
}

// ─── MediaAsset ───────────────────────────────────────────────────────────────

export interface MediaAsset {
  id: string;
  type: MediaAssetType;
  url: string;
  license: string;           // e.g. "CC-BY-4.0", "editorial", "rights-managed"
  caption: string;
  score: number;             // 0.0 → 1.0  relevance score assigned by media service
  metadata: MediaMetadata;
}

export interface MediaMetadata {
  width?: number;
  height?: number;
  duration_seconds?: number;
  file_size_bytes?: number;
  format?: string;
  alt_text?: string;
  source_credit?: string;
}

// ─── Publication ──────────────────────────────────────────────────────────────

export interface Publication {
  id: string;
  article: NewsArticle;
  channel: PublicationChannel;
  publish_date: string;       // ISO 8601 — can be future (scheduled)
  status: PublicationStatus;
  published_url: string | null;
}

// ─── Metrics / Analytics ──────────────────────────────────────────────────────

export interface ArticleMetrics {
  article_id: string;
  views: number;
  unique_visitors: number;
  avg_read_time_seconds: number;
  social_shares: number;
  comments: number;
  bounce_rate: number;        // 0.0 → 1.0
  recorded_at: string;
}
