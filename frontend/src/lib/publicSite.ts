/**
 * What the reader's machine-readable files share - the RSS feed
 * (app/reader/feed.xml), the sitemap (app/reader/sitemap.xml) and the
 * article pages' metadata (app/reader/[id]/layout.tsx): reading the
 * backend's open reader endpoints from the server, and the site's own
 * address for the absolute links those files must carry.
 *
 * Server-only: BACKEND_URL and the key never reach a browser, as in the
 * proxies under app/api/. Under /reader/ on purpose: Caddy serves only
 * /reader/* without the site password (docker/caddy/Caddyfile, @reader),
 * so a feed or sitemap anywhere else would sit behind it.
 */

import type { ReaderArticle, ReaderCard } from "@/lib/reader";
import type { StoryCard } from "@/lib/stories";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// The backend's page size cap on both lists (le=50).
const PAGE = 50;

// The sitemap's ceiling: past it the protocol wants an index of several
// files, which this site is far from needing (sitemaps.org: 50,000 URLs).
const SITEMAP_MAX = 5000;

function headers(): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;
  return apiKey ? { "X-API-Key": apiKey } : {};
}

/** A backend reader endpoint's JSON, or null for any failure (logged here, never shown). */
export async function backendJson<T>(path: string): Promise<T | null> {
  try {
    // no-store: a story is published or taken down at any moment (the
    // incident in app/api/jobs/[jobId]/route.ts).
    const response = await fetch(`${BACKEND_URL}${path}`, { cache: "no-store", headers: headers() });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch (exc) {
    console.error(`Could not read ${path} from the backend at ${BACKEND_URL}:`, exc);
    return null;
  }
}

/** Every item of a paged reader list, up to `max`, newest first as the backend orders them. */
async function everything<T>(path: string, max: number): Promise<T[] | null> {
  const items: T[] = [];

  for (let offset = 0; offset < max; offset += PAGE) {
    const page = await backendJson<{ total: number; items: T[] }>(`${path}?offset=${offset}&limit=${PAGE}`);
    if (!page) return offset === 0 ? null : items;
    items.push(...page.items);
    if (items.length >= page.total || page.items.length === 0) break;
  }

  return items.slice(0, max);
}

export function allStories(max = SITEMAP_MAX): Promise<StoryCard[] | null> {
  return everything<StoryCard>("/reader/stories", max);
}

export function allArticles(max = SITEMAP_MAX): Promise<ReaderCard[] | null> {
  return everything<ReaderCard>("/reader/articles", max);
}

export function readerArticle(id: string): Promise<ReaderArticle | null> {
  return /^[0-9a-f]{16}$/.test(id) ? backendJson<ReaderArticle>(`/reader/articles/${id}`) : Promise.resolve(null);
}

/**
 * The site's address, for absolute links. PUBLIC_SITE_URL when set (the
 * domain the site is served on); else what the request came in on, as
 * Caddy forwards it (X-Forwarded-Proto and -Host, else Host) - right
 * behind Caddy and in development alike.
 */
export function siteOrigin(request: Request): string {
  const configured = process.env.PUBLIC_SITE_URL;
  if (configured) return configured.replace(/\/+$/, "");

  const url = new URL(request.url);
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? url.host;
  const proto = request.headers.get("x-forwarded-proto") ?? url.protocol.replace(/:$/, "");

  return `${proto.split(",")[0].trim()}://${host.split(",")[0].trim()}`;
}

export function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * A backend timestamp as a Date. One without a zone is UTC - the
 * backend's convention, and the bug readerText's dateIn fixed: read as
 * local time it moves by the server's offset.
 */
export function utc(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(/T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(iso) ? `${iso}Z` : iso);
  return Number.isNaN(date.getTime()) ? null : date;
}
