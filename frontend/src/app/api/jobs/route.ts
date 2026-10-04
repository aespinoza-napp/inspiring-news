import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Every backend endpoint that costs CPU, starts a browser or writes data
// takes the API key once STORAGE_API_KEY is set (backend
// src/api/routes.py::require_storage_key), and production always sets
// it. Read here, on the server, so the key never reaches the browser.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get("limit") ?? "20";

  let response: Response;

  try {
    // no-store, for the same reason as app/api/jobs/[jobId]/route.ts: this
    // is polled every second, and Next.js caches server-side GET fetches by
    // default - the live screen would show the first snapshot forever.
    response = await fetch(
      `${BACKEND_URL}/analyze/jobs?limit=${encodeURIComponent(limit)}`,
      {
        cache: "no-store",
        headers: headers(false),
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
      headers: headers(true),
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
