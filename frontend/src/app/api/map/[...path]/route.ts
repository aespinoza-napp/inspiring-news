import { NextRequest, NextResponse } from "next/server";

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
function headers(request: NextRequest): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;
  const tag = request.headers.get("if-none-match");
  const forwarded = request.headers.get("x-forwarded-for");

  return {
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

  // As text: the map is relayed, not parsed, so a 10k-article document
  // costs no JSON round trip here. Response headers are set one by one,
  // never as an options object: test_api_key.py reads every `headers:`
  // in a proxy as a request's, which must come from headers().
  const relayed = new NextResponse(response.status === 304 ? null : await response.text(), { status: response.status });
  const tag = response.headers.get("etag");

  if (tag) relayed.headers.set("ETag", tag);
  relayed.headers.set("Cache-Control", "no-cache");
  if (response.status !== 304) relayed.headers.set("Content-Type", "application/json");

  return relayed;
}
