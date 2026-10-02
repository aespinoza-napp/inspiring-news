import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(_request: NextRequest, { params }: { params: { id: string } }) {
  let response: Response;

  try {
    // no-store, as in ../route.ts: a re-check can withdraw an article,
    // and a cached copy would go on showing it.
    // The key: see ../route.ts - the backend does not ask for it.
    const apiKey = process.env.STORAGE_API_KEY;

    response = await fetch(`${BACKEND_URL}/reader/articles/${encodeURIComponent(params.id)}`, {
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

  try {
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { error: `The backend answered ${response.status} without JSON.` },
      { status: 502 }
    );
  }
}
