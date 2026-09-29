import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// One proxy for the /graph/* family, but only for these paths: a
// catch-all that forwarded anything would turn this route into an open
// proxy onto every backend endpoint, with the storage key attached.
const GET_PATHS = new Set(["schema", "presets", "articles", "related"]);
const POST_PATHS = new Set(["query", "sync"]);

// Behind the backend's optional STORAGE_API_KEY. Read here, on the
// server, so the key never reaches the browser.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

async function relay(url: string, init: RequestInit) {
  let response: Response;

  try {
    response = await fetch(url, init);
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");

  if (!GET_PATHS.has(path)) {
    return NextResponse.json({ error: `Unknown graph endpoint: ${path}` }, { status: 404 });
  }

  // no-store: the graph changes after every analysis and every sync, and
  // Next.js caches server-side GET fetches by default (the same incident
  // as app/api/jobs/[jobId]/route.ts).
  return relay(`${BACKEND_URL}/graph/${path}${request.nextUrl.search}`, {
    cache: "no-store",
    headers: headers(false),
  });
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");

  if (!POST_PATHS.has(path)) {
    return NextResponse.json({ error: `Unknown graph endpoint: ${path}` }, { status: 404 });
  }

  const body = await request.text();

  return relay(`${BACKEND_URL}/graph/${path}`, {
    method: "POST",
    headers: headers(true),
    body: body || "{}",
  });
}
