import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// Every /dataset route is behind the backend's optional STORAGE_API_KEY:
// the writes land in a file that goes into git. Read here, on the server,
// so the key never reaches the browser.
export async function forward(path: string, init: { method: string; body?: unknown }) {
  const apiKey = process.env.STORAGE_API_KEY;

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      method: init.method,
      // no-store: the set changes with every label, and Next.js caches
      // server-side GET fetches by default (the incident behind
      // app/api/jobs/[jobId]/route.ts).
      cache: "no-store",
      headers: {
        ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  // A delete answers 204 with no body; NextResponse.json cannot carry one.
  if (response.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}
