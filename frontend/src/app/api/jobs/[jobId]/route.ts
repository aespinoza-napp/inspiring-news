import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/analyze/jobs/${params.jobId}`);
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
