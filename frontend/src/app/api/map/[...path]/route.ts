import { NextRequest, NextResponse } from "next/server";
import { gzipSync } from "zlib";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}.`;

// The news map's four backend routes (src/api/map_routes.py), and only
// these: a catch-all that forwarded anything would be an open proxy onto
// every backend endpoint, from a page anyone can open.
const ARTICLE_LINKS = /^articles\/[0-9a-f]{16}\/links$/;

function allowed(path: string): boolean {
  return path === "articles" || path === "entities" || path === "search" || ARTICLE_LINKS.test(path);
}

// Only these reach the backend, which validates them again.
const FORWARDED = ["day", "limit", "q", "semantic"];

// The backend leaves /map open on purpose, like /reader: it is what the
// public map shows anyone. The key is still sent when this server has
// one, so the map keeps working if a deployment gates every route; read
// here, on the server, never shipped to the browser.
// X-Forwarded-For is passed on because the backend limits searches per
// visitor (src/api/map_routes.py, client_of): without it every visitor
// would be this server, sharing one limit. Caddy sets it from the
// connection.
function headers(request: NextRequest, json = false): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;
  const tag = request.headers.get("if-none-match");
  const forwarded = request.headers.get("x-forwarded-for");

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
    ...(tag ? { "If-None-Match": tag } : {}),
    ...(forwarded ? { "X-Forwarded-For": forwarded } : {}),
  };
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join("/");

  if (!allowed(path)) {
    return NextResponse.json({ error: `Unknown map endpoint: ${path}` }, { status: 404 });
  }

  const query = new URLSearchParams();
  for (const name of FORWARDED) {
    const value = request.nextUrl.searchParams.get(name);
    if (value) query.set(name, value);
  }

  let response: Response;

  try {
    // no-store: the map changes whenever an article is published, and
    // Next.js caches server-side GET fetches by default (the incident in
    // app/api/jobs/[jobId]/route.ts). Revalidation is the browser's,
    // through the backend's ETag.
    response = await fetch(`${BACKEND_URL}/map/${path}?${query}`, { cache: "no-store", headers: headers(request) });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  // Relayed, not parsed, so a 10k-story document costs no JSON round
  // trip here. Compressed again for the browser: Node's fetch undoes the
  // backend's gzip, and Next.js does not compress a route handler's
  // answer - measured 29 Oct, 10k stories reached the browser as 2.09 MB
  // (scripts/bench_news_map.py). Level 4, as the backend found (21 ms
  // against 185 ms at 6, for 6% more bytes). Response headers are set one
  // by one, never as an options object: test_api_key.py reads every
  // `headers:` in a proxy as a request's, which must come from headers().
  const text = response.status === 304 ? null : await response.text();
  const gzip = text !== null && text.length > 1024 && (request.headers.get("accept-encoding") ?? "").includes("gzip");
  const relayed = new NextResponse(gzip ? gzipSync(text, { level: 4 }) : text, { status: response.status });
  const tag = response.headers.get("etag");

  if (tag) relayed.headers.set("ETag", tag);
  relayed.headers.set("Cache-Control", "no-cache");
  relayed.headers.set("Vary", "Accept-Encoding");
  if (gzip) relayed.headers.set("Content-Encoding", "gzip");
  if (response.status !== 304) relayed.headers.set("Content-Type", "application/json");

  return relayed;
}

// For you (backend POST /map/for-you): ranks the published stories for the
// profile it is sent and stores nothing. The only POST this proxy relays.
export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join("/");

  if (path !== "for-you") {
    return NextResponse.json({ error: `Unknown map endpoint: POST ${path}` }, { status: 404 });
  }

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/map/for-you`, {
      method: "POST",
      cache: "no-store",
      headers: headers(request, true),
      body: (await request.text()) || "{}",
    });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const relayed = new NextResponse(await response.text(), { status: response.status });
  relayed.headers.set("Content-Type", "application/json");
  relayed.headers.set("Cache-Control", "no-store");
  const wait = response.headers.get("retry-after");
  if (wait) relayed.headers.set("Retry-After", wait);

  return relayed;
}
