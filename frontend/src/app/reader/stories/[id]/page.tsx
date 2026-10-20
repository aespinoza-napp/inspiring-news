import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { LanguageSwitch } from "@/components/reader/LanguageSwitch";
import { StoryArticle } from "@/components/reader/StoryArticle";
import { pickLang, preferredLang, readerText, withLang } from "@/lib/readerText";
import { loadStory } from "./loadStory";

// Rendered per request, never at build time: a story is published and
// taken down while the site runs, and `next build` has no backend to ask
// (frontend/CLAUDE.md, "In production").
export const dynamic = "force-dynamic";

interface Props {
  params: { id: string };
  searchParams: { lang?: string | string[] };
}

/** `?lang=`, else the story's own language, else the browser's (Accept-Language), else English. */
function pageLang(searchParams: Props["searchParams"], storyLanguage?: string) {
  const chosen = Array.isArray(searchParams.lang) ? searchParams.lang[0] : searchParams.lang;
  return pickLang(chosen, storyLanguage, preferredLang(headers().get("accept-language")));
}

/**
 * The title and description a search engine and a shared link show:
 * the article's own title, and its SEO description (or its subtitle).
 */
export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const load = await loadStory(params.id);

  if (load.state !== "ready") {
    return { title: readerText(pageLang(searchParams)).storyNotFound };
  }

  const { story } = load;
  const description = story.metadata.seoDescription || story.content.subtitle || undefined;

  return {
    title: story.content.title,
    description,
    keywords: story.metadata.keywords.length ? story.metadata.keywords : undefined,
    openGraph: {
      type: "article",
      title: story.content.title,
      description,
      publishedTime: story.publishedAt,
      tags: story.metadata.tags.length ? story.metadata.tags : undefined,
      locale: story.language,
    },
  };
}

/**
 * A published article: the snapshot taken when a person published it,
 * never the draft behind it (docs/decisions/writing.md, "Publishing").
 * Public, like every /reader page (Caddy's @reader), so nothing here
 * edits, approves or unpublishes - that is /drafts/[id].
 *
 * The page around the story speaks the story's language unless the
 * reader chose another; it is wrapped in an element carrying that `lang`,
 * since the root layout's <html lang="en"> serves the operator pages too.
 */
export default async function StoryPage({ params, searchParams }: Props) {
  const load = await loadStory(params.id);

  // A real 404, so a withdrawn story drops out of search results.
  if (load.state === "missing") notFound();

  const lang = pageLang(searchParams, load.state === "ready" ? load.story.language : undefined);
  const t = readerText(lang);

  return (
    <div lang={lang}>
      <div className="reader-top">
        <p className="reader-back">
          <Link href={withLang("/reader", lang)}>{t.backToFeed}</Link>
        </p>
        <LanguageSwitch lang={lang} hrefFor={(code) => withLang(`/reader/stories/${params.id}`, code)} />
      </div>

      {load.state === "error" ? (
        <div className="error-banner" role="alert">
          {t.storyFailed}
        </div>
      ) : (
        <StoryArticle story={load.story} lang={lang} />
      )}
    </div>
  );
}
