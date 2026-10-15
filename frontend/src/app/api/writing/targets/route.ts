import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// GET /writing/targets: the default target of each review metric and the
// bounds of a rewrite request (backend src/api/rewrite_routes.py), for
// RewritePanel on /drafts/[id]. Its own proxy, not one of app/api/drafts'
// actions: the backend cannot serve it at /drafts/targets, where
// GET /drafts/{draft_id} answers first with a 422 - as with
// /publishing/channels. Behind the site password like /drafts (not under
// /api/reader), and behind the API key on the backend.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export async function GET() {
  let response: Response;

  try {
    // no-store: without it, this request-less GET would be prerendered
    // at build time against a backend that is not there
    // (frontend/CLAUDE.md, "In production").
    response = await fetch(`${BACKEND_URL}/writing/targets`, {
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
