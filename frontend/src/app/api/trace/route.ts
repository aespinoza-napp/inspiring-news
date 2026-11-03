import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// One article's journey (backend GET /trace, src/services/trace.py): the
// lineage, rejected runs included, so it takes the storage key like
// /storage/*. Read here, on the server, so the key never reaches the browser.
function headers(): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return apiKey ? { "X-API-Key": apiKey } : {};
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim() ?? "";

  if (!q) {
    return NextResponse.json({ error: "Paste an article URL or an id." }, { status: 400 });
  }

  let response: Response;

  try {
    // no-store: a trace is asked again while a run is still writing, and
    // Next.js caches server-side GET fetches by default (the incident in
    // app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/trace?q=${encodeURIComponent(q)}`, {
      cache: "no-store",
      headers: headers(),
    });
  } catch {
    return NextResponse.json(
      {
        error: `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`,
      },
      { status: 502 }
    );
  }

  const data = await response.json().catch(() => ({ error: `The backend answered ${response.status}.` }));

  return NextResponse.json(data, { status: response.status });
}
