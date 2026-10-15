import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// The writing flow (docs/decisions/writing.md). Like ingest/rounds, this
// proxy names what it relays: a draft id is 16 hex characters and an
// action one of the stages below. Anything else is not forwarded with
// the storage key attached.
const DRAFT_ID = /^[0-9a-f]{16}$/;

// One per stage, declared up front so no stage edits another's line.
const POST_ACTIONS = new Set(["review", "accept-correction", "rewrite", "restore", "approve", "publish", "unpublish"]);
const PUT_ACTIONS = new Set(["content"]);

// Every /drafts endpoint takes the API key once STORAGE_API_KEY is set
// (backend src/api/draft_routes.py). Read here, on the server, so the key
// never reaches the browser.
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

  const text = await response.text();

  try {
    return NextResponse.json(JSON.parse(text), { status: response.status });
  } catch {
    return NextResponse.json(
      { error: `The backend answered ${response.status} with something that is not JSON.` },
      { status: 502 }
    );
  }
}

function notFound(path: string[]) {
  return NextResponse.json({ error: `Unknown drafts endpoint: ${path.join("/")}` }, { status: 404 });
}

// GET /api/drafts        -> every draft, no bodies
// GET /api/drafts/<id>   -> one draft, polled while it is busy
export async function GET(_request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ?? [];

  if (path.length > 1 || (path.length === 1 && !DRAFT_ID.test(path[0]))) {
    return notFound(path);
  }

  // no-store: a draft changes while it is written, reviewed or rewritten,
  // and Next.js caches server-side GET fetches by default (the incident
  // behind app/api/jobs/[jobId]/route.ts).
  return relay(`${BACKEND_URL}/drafts${path.length ? `/${path[0]}` : ""}`, {
    cache: "no-store",
    headers: headers(false),
  });
}

// The body is relayed as sent and validated by the backend.
//
// POST /api/drafts               -> write a new draft
// POST /api/drafts/<id>/<action> -> one of POST_ACTIONS
export async function POST(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ?? [];

  const create = path.length === 0;
  const action = path.length === 2 && DRAFT_ID.test(path[0]) && POST_ACTIONS.has(path[1]);

  if (!create && !action) {
    return notFound(path);
  }

  const body = await request.text();

  return relay(`${BACKEND_URL}/drafts${create ? "" : `/${path[0]}/${path[1]}`}`, {
    method: "POST",
    headers: headers(true),
    body: body || "{}",
  });
}

// PUT /api/drafts/<id>/content -> a person's edit
export async function PUT(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ?? [];

  if (!(path.length === 2 && DRAFT_ID.test(path[0]) && PUT_ACTIONS.has(path[1]))) {
    return notFound(path);
  }

  const body = await request.text();

  return relay(`${BACKEND_URL}/drafts/${path[0]}/${path[1]}`, {
    method: "PUT",
    headers: headers(true),
    body: body || "{}",
  });
}
