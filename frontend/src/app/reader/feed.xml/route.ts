import { badgeVerdict, notJudgedReasons, tally } from "@/lib/reader";
import { allArticles, allStories, escapeXml, siteOrigin, utc } from "@/lib/publicSite";
import { pickLang, readerText, withLang } from "@/lib/readerText";

// Per request: the feed follows what is published, and has no build-time
// backend to read (frontend/CLAUDE.md, "In production").
export const dynamic = "force-dynamic";

// How many items a reader's feed app gets: the newest of both kinds.
const ITEMS = 50;

/**
 * The reader as RSS 2.0: the newsroom's own articles and the checked
 * news, in one feed, newest first (roadmap, Phase 6). `?lang=` words the
 * channel and each item's verdict line (Catalan, Spanish or English); the
 * headlines and excerpts stay in their own language. Links carry the same
 * `lang`, so a reader lands on the page in the language they subscribed in.
 */
export async function GET(request: Request) {
  const lang = pickLang(new URL(request.url).searchParams.get("lang"));
  const t = readerText(lang);
  const origin = siteOrigin(request);

  const [stories, articles] = await Promise.all([allStories(ITEMS), allArticles(ITEMS)]);

  if (stories === null && articles === null) {
    return new Response("The feed is unavailable just now.", { status: 503, headers: { "Retry-After": "300" } });
  }

  const items = [
    ...(stories ?? []).map((story) => ({
      date: utc(story.publishedAt),
      title: story.title,
      link: `${origin}${withLang(`/reader/stories/${story.id}`, lang)}`,
      guid: `${origin}/reader/stories/${story.id}`,
      description: [t.disclosureShort(story.disclosure.aiWritten, story.disclosure.humanEdited), story.subtitle || story.description]
        .filter(Boolean)
        .join(" · "),
      category: t.newsroomTitle,
    })),
    ...(articles ?? []).map((article) => {
      const verdict = badgeVerdict(article.verdict);
      const label = verdict ? t.verdict[verdict] : t.notChecked;
      // As the feed's cards say it: the judged claims, then those we
      // failed to check, counted apart - or, with none judged, why.
      const detail = [
        tally(article.verdict, t),
        verdict && article.verdict.notJudged > 0 ? t.notCheckedCount(article.verdict.notJudged) : "",
        verdict ? "" : notJudgedReasons(article.verdict, t),
      ]
        .filter(Boolean)
        .join(", ");
      return {
        // When it reached the reader, else when its outlet published it.
        date: utc(article.checkedAt) ?? utc(article.publishedAt),
        title: article.headline,
        link: `${origin}${withLang(`/reader/${article.id}`, lang)}`,
        guid: `${origin}/reader/${article.id}`,
        description: [t.rssVerdict(label, detail), article.excerpt].filter(Boolean).join(" — "),
        category: article.source.name,
      };
    }),
  ]
    .sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0))
    .slice(0, ITEMS);

  const self = `${origin}/reader/feed.xml${lang === "en" ? "" : `?lang=${lang}`}`;

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "<channel>",
    `<title>${escapeXml(t.rssTitle)}</title>`,
    `<link>${escapeXml(`${origin}${withLang("/reader", lang)}`)}</link>`,
    `<description>${escapeXml(t.rssDescription)}</description>`,
    `<language>${lang}</language>`,
    `<atom:link href="${escapeXml(self)}" rel="self" type="application/rss+xml"/>`,
    ...(items[0]?.date ? [`<lastBuildDate>${items[0].date.toUTCString()}</lastBuildDate>`] : []),
    ...items.map((item) =>
      [
        "<item>",
        `<title>${escapeXml(item.title)}</title>`,
        `<link>${escapeXml(item.link)}</link>`,
        `<guid isPermaLink="true">${escapeXml(item.guid)}</guid>`,
        ...(item.date ? [`<pubDate>${item.date.toUTCString()}</pubDate>`] : []),
        `<category>${escapeXml(item.category)}</category>`,
        `<description>${escapeXml(item.description)}</description>`,
        "</item>",
      ].join("")
    ),
    "</channel>",
    "</rss>",
  ].join("\n");

  return new Response(xml, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8", "Cache-Control": "public, max-age=300" },
  });
}
