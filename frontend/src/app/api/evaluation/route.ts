import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// The summary hands out whole labelled records, so it is behind the
// backend's STORAGE_API_KEY like every other read of stored data. Read
// here, on the server, so the key never reaches the browser.
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
    // no-store: a fact saved in the labeller should show on the next
    // refresh, and Next.js caches server-side GET fetches by default
    // (the incident behind app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/evaluation/summary`, {
      cache: "no-store",
      headers: headers(false),
    });
  } catch {
    return NextResponse.json(
      {
        error: `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`,
      },
      { status: 502 }
    );
  }

  let data: unknown;

  try {
    data = await response.json();
  } catch {
    // A proxy's HTML error page, or a backend too old to have the route.
    return NextResponse.json(
      { error: `The backend answered ${response.status} without JSON.` },
      { status: 502 }
    );
  }

  return NextResponse.json(data, { status: response.status });
}
