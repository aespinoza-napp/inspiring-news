import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Only these are forwarded: the backend validates them, and anything
// else on the query string has no business reaching it.
const FORWARDED = ["topic", "language", "offset", "limit"];

// The backend leaves the /reader routes open on purpose: it is what this page
// shows anyone. The key is still sent when this server has one, so the
// page keeps working if a deployment gates every route; it is read here,
// on the server, and never reaches the browser.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function GET(request: NextRequest) {
  const query = new URLSearchParams();

  for (const name of FORWARDED) {
    const value = request.nextUrl.searchParams.get(name);
    if (value) query.set(name, value);
  }

  let response: Response;

  try {
    // no-store: Next.js caches server-side GET fetches by default, and
    // the feed changes whenever an analysis finishes - a cached copy
    // would hide every article published after the first visit (the
    // incident in app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/reader/articles?${query}`, {
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

  return relay(response);
}

/** The backend's JSON and status, or a 502 that says what came back instead. */
async function relay(response: Response) {
  try {
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { error: `The backend answered ${response.status} without JSON.` },
      { status: 502 }
    );
  }
}
