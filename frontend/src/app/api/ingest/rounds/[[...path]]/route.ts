import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// The backend mints round ids as 16 hex characters. Anything else is not
// forwarded: like graph/[...path], this proxy names what it relays rather
// than passing any path through with the storage key attached.
const ROUND_ID = /^[0-9a-f]{16}$/;
const ACTIONS = new Set(["ai-selection", "queue", "more", "person-selection", "reject"]);

// A photo kept with a round (backend src/services/selection/photos.py):
// the names it gives, nothing else.
const PHOTO = /^[0-9a-f]{16}\.(jpg|png|gif|webp|avif)$/;

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

// A kept photo, relayed as the bytes and type the backend serves: the
// browser never holds the key, so an <img> asks here.
async function relayPhoto(url: string) {
  let response: Response;

  try {
    response = await fetch(url, { cache: "no-store", headers: headers(false) });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  if (!response.ok) {
    return NextResponse.json({ error: "No such photo." }, { status: response.status });
  }

  // The photo's own type, as packages/[[...path]] relays a file, and
  // nothing else of the backend's response. Set one by one: a `headers:`
  // here would read, to test_api_key.py, as a request sent without the key.
  const relayed = new NextResponse(await response.arrayBuffer(), { status: 200 });
  relayed.headers.set("Content-Type", response.headers.get("content-type") ?? "application/octet-stream");
  relayed.headers.set("X-Content-Type-Options", "nosniff");
  relayed.headers.set("Cache-Control", "private, max-age=604800");

  return relayed;
}

// GET /api/ingest/rounds                       -> the newest rounds
// GET /api/ingest/rounds/<id>                  -> one round, polled while its AI selection runs
// GET /api/ingest/rounds/<id>/photos/<name>    -> a compared pick's kept photo
export async function GET(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path ?? [];

  if (path.length === 3 && ROUND_ID.test(path[0]) && path[1] === "photos" && PHOTO.test(path[2])) {
    return relayPhoto(`${BACKEND_URL}/ingest/rounds/${path[0]}/photos/${path[2]}`);
  }

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

// The body is relayed as sent and validated by the backend (a bad
// `topicEmphasis` or `listed` comes back as its 422), so a new round field
// needs no change here - only the path is checked.
//
// POST /api/ingest/rounds                    -> discover candidates
// POST /api/ingest/rounds/<id>/ai-selection  -> start the AI selection
// POST /api/ingest/rounds/<id>/queue         -> send the chosen ones to analysis
// POST /api/ingest/rounds/<id>/more          -> show the next ranked candidates, up to 40
// POST /api/ingest/rounds/<id>/person-selection -> record a person's own five, to compare with the AI's
// POST /api/ingest/rounds/<id>/reject           -> mark a candidate not for us (or take it back)
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
