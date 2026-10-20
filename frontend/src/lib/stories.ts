/**
 * The newsroom's published articles as the public reader sees them: the
 * shapes `GET /reader/stories` and `GET /reader/stories/{id}` return
 * (backend/src/services/publishing/story.py), and the helpers the story
 * page and the reader's list share.
 *
 * A snapshot taken when a person published the draft, not the draft:
 * nothing here has the instructions, the revisions or the review, and
 * nothing on a /reader page should go looking for them. Kept apart from
 * lib/drafts.ts for the same reason lib/reader.ts is kept apart from
 * lib/types.ts - a different audience, changing for different reasons.
 */

import { DraftLanguage, SourceOrigin } from "@/lib/drafts";
import { Verdict } from "@/lib/types";

export interface StoryDisclosure {
  /** Always true today: every draft starts from the writer model. */
  aiWritten: boolean;
  /** Each model whose text became the article, in the order they wrote. */
  models: string[];
  /** A person changed the text as well as approving it. */
  humanEdited: boolean;
}

export interface StorySource {
  url: string;
  title: string;
  domain: string;
  origin: SourceOrigin;
  publishedAt: string | null;
}

export interface StoryFactCheck {
  claim: string;
  verdict: string;
  confidence: number | null;
  sourceUrls: string[];
}

export interface StoryMetadata {
  slug: string;
  seoDescription: string;
  keywords: string[];
  topic: string | null;
  tags: string[];
}

export interface PublishedStory {
  /** The draft's id; the page is /reader/stories/<id>. */
  id: string;
  /** The analysed article's reader id: /reader/<id>. */
  sourceArticleId: string;
  language: DraftLanguage;
  /** `body` is Markdown; [n] cites sources[n - 1]. */
  content: { title: string; subtitle: string; body: string };
  sources: StorySource[];
  factChecks: StoryFactCheck[];
  metadata: StoryMetadata;
  disclosure: StoryDisclosure;
  publishedAt: string;
}

export interface StoryCard {
  id: string;
  language: DraftLanguage;
  title: string;
  subtitle: string;
  /** The article's SEO description; may be empty. */
  description: string;
  topic: string | null;
  publishedAt: string;
  sourceArticleId: string;
  disclosure: StoryDisclosure;
}

export interface StoryFeed {
  total: number;
  offset: number;
  limit: number;
  items: StoryCard[];
  topics: { topic: string; count: number }[];
  languages: { language: string; count: number }[];
  /** Published at all, whatever the filters. */
  published: number;
}

export const STORY_ID = /^[0-9a-f]{16}$/;

export function storyPath(id: string): string {
  return `/reader/stories/${id}`;
}

// The words around a story - its language's name, its date, the
// disclosure, the sources' origins - are in lib/readerText.ts, in the
// page's language (Catalan, Spanish or English).

const VERDICTS: Verdict[] = ["TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING", "UNVERIFIED"];

/** A fact-check's verdict for VerdictBadge; anything else reads "Not checked". */
export function verdictOf(value: string): Verdict | null {
  const upper = value.toUpperCase() as Verdict;
  return VERDICTS.includes(upper) ? upper : null;
}
