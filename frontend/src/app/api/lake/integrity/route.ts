import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Whether the lake's lineage holds together (backend GET /lake/integrity,
// src/services/lake_integrity.py). Takes the storage key, read here, on the
// server, so it never reaches the browser.
function headers(): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return apiKey ? { "X-API-Key": apiKey } : {};
}

export async function GET() {
  let response: Response;

  try {
    // no-store: this route takes no request argument, so without it the
    // build would prerender it against a backend that is not there.
    response = await fetch(`${BACKEND_URL}/lake/integrity`, { cache: "no-store", headers: headers() });
  } catch {
    return NextResponse.json(
      { error: `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)` },
      { status: 502 }
    );
  }

  const data = await response.json().catch(() => ({ error: `The backend answered ${response.status}.` }));

  return NextResponse.json(data, { status: response.status });
}
