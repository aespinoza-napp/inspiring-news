import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// What the person taught the ranking on /discover (backend
// src/services/selection/feedback.py). Like rounds/[[...path]], this proxy
// names the two paths it relays rather than passing any through with the
// storage key attached.
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

function notFound(path: string[]) {
  return NextResponse.json({ error: `Unknown feedback endpoint: ${path.join("/")}` }, { status: 404 });
}

// GET /api/ingest/feedback?edition=   -> every rejection and blocked site of the edition
export async function GET(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path ?? [];

  if (path.length > 0) {
    return notFound(path);
  }

  const edition = request.nextUrl.searchParams.get("edition") === "devastating" ? "devastating" : "positive";

  // no-store: it changes with every rejection, and Next.js caches server-side GETs.
  return relay(`${BACKEND_URL}/ingest/feedback?edition=${edition}`, {
    cache: "no-store",
    headers: headers(false),
  });
}

// POST /api/ingest/feedback/forget    -> take back one rejection or blocked site
export async function POST(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path ?? [];

  if (path.length !== 1 || path[0] !== "forget") {
    return notFound(path);
  }

  const body = await request.text();

  return relay(`${BACKEND_URL}/ingest/feedback/forget`, {
    method: "POST",
    headers: headers(true),
    body: body || "{}",
  });
}
