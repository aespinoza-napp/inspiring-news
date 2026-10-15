import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { StoryArticle } from "@/components/reader/StoryArticle";
import { loadStory } from "./loadStory";

// Rendered per request, never at build time: a story is published and
// taken down while the site runs, and `next build` has no backend to ask
// (frontend/CLAUDE.md, "In production").
export const dynamic = "force-dynamic";

/**
 * The title and description a search engine and a shared link show:
 * the article's own title, and its SEO description (or its subtitle).
 */
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const load = await loadStory(params.id);

  if (load.state !== "ready") {
    return { title: "Story not found" };
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
    },
  };
}

/**
 * A published article: the snapshot taken when a person published it,
 * never the draft behind it (docs/decisions/writing.md, "Publishing").
 * Public, like every /reader page (Caddy's @reader), so nothing here
 * edits, approves or unpublishes - that is /drafts/[id].
 */
export default async function StoryPage({ params }: { params: { id: string } }) {
  const load = await loadStory(params.id);

  // A real 404, so a withdrawn story drops out of search results.
  if (load.state === "missing") notFound();

  return (
    <>
      <p className="reader-back">
        <Link href="/reader">← Checked articles</Link>
      </p>

      {load.state === "error" ? (
        <div className="error-banner" role="alert">
          This article could not be loaded just now. Try again in a moment.
        </div>
      ) : (
        <StoryArticle story={load.story} />
      )}
    </>
  );
}
