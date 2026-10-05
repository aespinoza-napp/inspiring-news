import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// The backend mints round ids as 16 hex characters. Anything else is not
// forwarded: like graph/[...path], this proxy names what it relays rather
// than passing any path through with the storage key attached.
const ROUND_ID = /^[0-9a-f]{16}$/;
const ACTIONS = new Set(["ai-selection", "queue"]);

// Every backend endpoint that costs CPU, starts a browser or writes data
// takes the API key once STORAGE_API_KEY is set (backend
// src/api/routes.py::require_storage_key), and production always sets
// it. Read here, on the server, so the key never reaches the browser.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

async function relay(url: string, init: RequestInit) {
  let response: Response;

  try {
    response = await fetch(url, init);
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const data = await response.json();

  return NextResponse.json(data, { status: response.status });
}

function notFound(path: string[]) {
  return NextResponse.json({ error: `Unknown round endpoint: ${path.join("/")}` }, { status: 404 });
}

// GET /api/ingest/rounds            -> the newest rounds
// GET /api/ingest/rounds/<id>       -> one round, polled while its AI selection runs
export async function GET(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path ?? [];

  if (path.length > 1 || (path.length === 1 && !ROUND_ID.test(path[0]))) {
    return notFound(path);
  }

  // no-store: a round changes while its AI selection runs, and Next.js
  // caches server-side GET fetches by default (the incident behind
  // app/api/jobs/[jobId]/route.ts).
  const target = path.length ? `/ingest/rounds/${path[0]}` : `/ingest/rounds${request.nextUrl.search}`;

  return relay(`${BACKEND_URL}${target}`, {
    cache: "no-store",
    headers: headers(false),
  });
}

// POST /api/ingest/rounds                    -> discover candidates
// POST /api/ingest/rounds/<id>/ai-selection  -> start the AI selection
// POST /api/ingest/rounds/<id>/queue         -> send the chosen ones to analysis
export async function POST(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path ?? [];

  const create = path.length === 0;
  const action = path.length === 2 && ROUND_ID.test(path[0]) && ACTIONS.has(path[1]);

  if (!create && !action) {
    return notFound(path);
  }

  const body = await request.text();

  return relay(`${BACKEND_URL}/ingest/rounds${create ? "" : `/${path[0]}/${path[1]}`}`, {
    method: "POST",
    headers: headers(true),
    body: body || "{}",
  });
}
