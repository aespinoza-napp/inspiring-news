import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// Behind the backend's optional STORAGE_API_KEY: a check sends real
// requests to every configured site. Read here, on the server, so the key
// never reaches the browser.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function GET() {
  let response: Response;

  try {
    // no-store: the last check's report changes after every run, and
    // Next.js caches server-side GET fetches by default (the same
    // incident as app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/sources/check`, {
      cache: "no-store",
      headers: headers(false),
    });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/sources/check`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}
