import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  const body = await request.json();

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/analyze/jobs/batch`, {
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

export async function GET(request: NextRequest) {
  const ids = request.nextUrl.searchParams.get("ids") ?? "";

  let response: Response;

  try {
    // no-store: polled every second the same way jobs/[jobId]/route.ts
    // is - see that file for the incident this guards against (Next.js
    // caching the first response and serving it forever).
    response = await fetch(
      `${BACKEND_URL}/analyze/jobs/batch?ids=${encodeURIComponent(ids)}`,
      { cache: "no-store" }
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
