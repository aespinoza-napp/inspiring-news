import { NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// GET /publishing/channels: where a draft can be published, and why a
// channel cannot (backend src/api/publish_routes.py). Its own proxy, not
// one of app/api/drafts' actions: the backend cannot serve it at
// /drafts/channels, where GET /drafts/{draft_id} answers first with a
// 422. Behind the site password like /drafts - it is not under
// /api/reader - and behind the API key on the backend.
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
    response = await fetch(`${BACKEND_URL}/publishing/channels`, {
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
