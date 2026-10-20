import { allArticles, allStories, escapeXml, siteOrigin, utc } from "@/lib/publicSite";
import { READER_LANGS, withLang } from "@/lib/readerText";

export const dynamic = "force-dynamic";

/**
 * Every public page, for a search engine: the reader, the guide, each of
 * our stories and each checked article - with its other two languages as
 * alternates (`hreflang`, the same page under `?lang=`). Under /reader/
 * because Caddy serves nothing else without the password; a robots.txt
 * would have to name this address, and the site has none yet.
 */
export async function GET(request: Request) {
  const origin = siteOrigin(request);
  const [stories, articles] = await Promise.all([allStories(), allArticles()]);

  if (stories === null && articles === null) {
    return new Response("The sitemap is unavailable just now.", { status: 503, headers: { "Retry-After": "300" } });
  }

  const pages: { path: string; modified: Date | null }[] = [
    { path: "/reader", modified: null },
    { path: "/reader/guide", modified: null },
    ...(stories ?? []).map((story) => ({ path: `/reader/stories/${story.id}`, modified: utc(story.publishedAt) })),
    ...(articles ?? []).map((article) => ({ path: `/reader/${article.id}`, modified: utc(article.checkedAt) })),
  ];

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ...pages.map((page) =>
      [
        "<url>",
        `<loc>${escapeXml(origin + page.path)}</loc>`,
        ...(page.modified ? [`<lastmod>${page.modified.toISOString().slice(0, 10)}</lastmod>`] : []),
        ...READER_LANGS.map(
          (lang) =>
            `<xhtml:link rel="alternate" hreflang="${lang}" href="${escapeXml(origin + withLang(page.path, lang))}"/>`
        ),
        `<xhtml:link rel="alternate" hreflang="x-default" href="${escapeXml(origin + page.path)}"/>`,
        "</url>",
      ].join("")
    ),
    "</urlset>",
  ].join("\n");

  return new Response(xml, {
    headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
