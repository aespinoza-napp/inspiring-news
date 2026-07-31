import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  let response: Response;

  try {
    // no-store: this is polled every second to follow job progress. Next.js
    // caches GET fetches by default (its Data Cache), which would otherwise
    // serve the first response forever - reproduced live: polling kept
    // returning 200 with the same stale "initializing" snapshot even after
    // the backend had finished the job (and, after a backend restart, even
    // after the backend no longer recognized the job id at all).
    response = await fetch(`${BACKEND_URL}/analyze/jobs/${params.jobId}`, {
      cache: "no-store",
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
