import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// Behind the backend's optional STORAGE_API_KEY: one probe sends requests
// to every configured site. Read here, on the server, so the key never
// reaches the browser.
function headers(json = false): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function GET() {
  let response: Response;

  try {
    // no-store: the panel polls this while a probe runs, and Next.js
    // caches server-side GET fetches by default - it would say "running"
    // forever (the same incident as app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/scraper/probe`, {
      cache: "no-store",
      headers: headers(),
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
    response = await fetch(`${BACKEND_URL}/scraper/probe`, {
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
