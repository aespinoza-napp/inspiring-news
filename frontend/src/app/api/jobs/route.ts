import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get("limit") ?? "20";

  let response: Response;

  try {
    // no-store, for the same reason as app/api/jobs/[jobId]/route.ts: this
    // is polled every second, and Next.js caches server-side GET fetches by
    // default - the live screen would show the first snapshot forever.
    // The list is behind the backend's optional STORAGE_API_KEY. It is read
    // here, on the server, so the key never reaches the browser.
    const apiKey = process.env.STORAGE_API_KEY;

    response = await fetch(
      `${BACKEND_URL}/analyze/jobs?limit=${encodeURIComponent(limit)}`,
      {
        cache: "no-store",
        headers: apiKey ? { "X-API-Key": apiKey } : undefined,
      }
    );
  } catch {
    return NextResponse.json(
      {
        error: `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`,
      },
      { status: 502 }
    );
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/analyze/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      {
        error: `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`,
      },
      { status: 502 }
    );
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}
