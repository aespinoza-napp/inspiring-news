import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  let response: Response;

  try {
    // no-store: the last run's report changes after every ingest, and
    // Next.js caches server-side GET fetches by default - it would show
    // the first report forever (the same incident as
    // app/api/jobs/[jobId]/route.ts).
    // Behind the backend's optional STORAGE_API_KEY, read here on the
    // server so the key never reaches the browser.
    const apiKey = process.env.STORAGE_API_KEY;

    response = await fetch(`${BACKEND_URL}/ingest/sources`, {
      cache: "no-store",
      headers: apiKey ? { "X-API-Key": apiKey } : undefined,
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
