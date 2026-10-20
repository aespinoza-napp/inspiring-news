import type { Metadata } from "next";
import { headers } from "next/headers";
import { badgeVerdict } from "@/lib/reader";
import { readerArticle } from "@/lib/publicSite";
import { pickLang, preferredLang, readerText } from "@/lib/readerText";

/**
 * The article page is a client component (it fetches through the proxy
 * and re-renders as the reader switches language), and a client page
 * cannot export metadata. This layout, on the server, gives it what a
 * search engine and a shared link show: the headline, the verdict and
 * the excerpt (roadmap, Phase 6: "metadata for /reader/[id]").
 *
 * A layout gets no search params, so the description's language is the
 * browser's (Accept-Language), else the article's own.
 */
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const article = await readerArticle(params.id);

  if (!article) return {};

  const t = readerText(pickLang(preferredLang(headers().get("accept-language")), article.language));
  const verdict = badgeVerdict(article.verdict);
  const description = t.metaDescription(verdict ? t.verdict[verdict] : t.notChecked, article.excerpt);

  return {
    title: article.headline,
    description,
    openGraph: {
      type: "article",
      title: article.headline,
      description,
      publishedTime: article.publishedAt ?? undefined,
      locale: article.language ?? undefined,
    },
  };
}

export default function ReaderArticleLayout({ children }: { children: React.ReactNode }) {
  return children;
}
