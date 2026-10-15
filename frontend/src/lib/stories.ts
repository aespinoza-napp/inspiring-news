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

const LANGUAGE_NAMES: Record<string, string> = {
  ca: "Catalan",
  es: "Spanish",
  en: "English",
};

/**
 * "15 Oct 2026", the same on every machine. The story page renders on the
 * server, where lib/reader.ts's readableDate (the runtime's locale) would
 * give the server's locale - on the laptop this was built on, Spanish -
 * in an English page. The stamp is UTC (backend draft_store.now()).
 */
export function storyDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

/** lib/reader.ts's languageName knows the two source languages; a story can also be Catalan. */
export function storyLanguageName(code: string): string {
  return LANGUAGE_NAMES[code.toLowerCase()] ?? code.toUpperCase();
}

export const ORIGIN_LABEL: Record<SourceOrigin, string> = {
  analysed: "The article we checked",
  related: "Related coverage",
  evidence: "Evidence behind a fact-check",
};

const VERDICTS: Verdict[] = ["TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING", "UNVERIFIED"];

/** A fact-check's verdict for VerdictBadge; anything else reads "Not checked". */
export function verdictOf(value: string): Verdict | null {
  const upper = value.toUpperCase() as Verdict;
  return VERDICTS.includes(upper) ? upper : null;
}

/**
 * The AI disclosure, said the same way on the card and the page. Names
 * the model: the reader's own pages name the model that checked an
 * article, and an AI-written article on a public page says so
 * (docs/decisions/writing.md, "Publishing").
 */
export function disclosureText(disclosure: StoryDisclosure): string {
  // Only what the record shows: a person approved every published
  // article, and `humanEdited` says whether they also changed the text.
  const person = disclosure.humanEdited
    ? "edited and approved for publication by a person on our team"
    : "approved for publication by a person on our team";

  if (!disclosure.aiWritten) {
    return `Written by our newsroom from the sources listed below, and ${person}.`;
  }

  const who =
    disclosure.models.length === 0
      ? "an AI model"
      : disclosure.models.length === 1
        ? `an AI model (${disclosure.models[0]})`
        : `AI models (${disclosure.models.join(", ")})`;

  return `Written by ${who} from the sources listed below, then ${person}.`;
}

/** The short form, for a card. */
export function disclosureShort(disclosure: StoryDisclosure): string {
  if (!disclosure.aiWritten) return "Written by our newsroom";
  return disclosure.humanEdited ? "Written with AI · edited and approved by a person" : "Written with AI · approved by a person";
}
