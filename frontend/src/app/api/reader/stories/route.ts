import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Only these are forwarded: the backend validates them, and anything
// else on the query string has no business reaching it.
const FORWARDED = ["topic", "language", "offset", "limit"];

// The newsroom's published articles (backend src/api/publish_routes.py,
// "Public"). Open on the backend like /reader/articles, and public here
// (Caddy's @reader covers /api/reader/*): it returns the published
// snapshots' cards, never a draft. The key is still sent when this
// server has one, so closing the route later is a backend-only change;
// it is read here, on the server, and never reaches the browser.
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
    // no-store: Next.js caches server-side GET fetches by default, and a
    // story is published or taken down at any moment - a cached list
    // would go on linking to a page that is gone (the incident in
    // app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/reader/stories?${query}`, {
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

  try {
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { error: `The backend answered ${response.status} without JSON.` },
      { status: 502 }
    );
  }
}
