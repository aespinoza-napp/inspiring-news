import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}. Is it running? (cd backend && uv run uvicorn src.main:app --reload)`;

// Ready-to-post packages (backend src/api/package_routes.py). Like the
// drafts proxy, this names what it relays - a draft id and a package id
// are 16 hex characters, a file one the backend's channels write - and
// forwards nothing else with the storage key attached. Its own proxy, not
// the drafts one, because it also relays binary files (the zip, the PNGs,
// a video) as they came.
const ID = /^[0-9a-f]{16}$/;
const FILE = /^(wordpress|instagram|stories|tiktok)\/[a-z0-9-]+\.(png|mp4|txt|json|xml)$/;

function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

function notFound(path: string[]) {
  return NextResponse.json({ error: `Unknown packages endpoint: ${path.join("/")}` }, { status: 404 });
}

async function relayJson(url: string, init: RequestInit) {
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

async function relayFile(url: string) {
  let response: Response;

  try {
    response = await fetch(url, { cache: "no-store", headers: headers(false) });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  if (!response.ok) {
    return relayJsonFrom(response);
  }

  // The file's own type, name and length, and nothing else of the
  // backend's response.
  const relayed = new NextResponse(response.body, { status: response.status });
  for (const name of ["content-type", "content-disposition", "content-length"]) {
    const value = response.headers.get(name);
    if (value) relayed.headers.set(name, value);
  }

  return relayed;
}

async function relayJsonFrom(response: Response) {
  const text = await response.text();

  try {
    return NextResponse.json(JSON.parse(text), { status: response.status });
  } catch {
    return NextResponse.json({ error: `The backend answered ${response.status}.` }, { status: response.status });
  }
}

// GET /api/packages/<draft>                         -> the draft's packages and the channels
// GET /api/packages/<draft>/<package>               -> one manifest
// GET /api/packages/<draft>/<package>/zip           -> the whole package
// GET /api/packages/<draft>/<package>/files/<c>/<f> -> one file it names
export async function GET(_request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ?? [];
  const [draft, pkg, action, ...rest] = path;

  if (!draft || !ID.test(draft)) return notFound(path);

  const base = `${BACKEND_URL}/drafts/${draft}/packages`;

  // no-store everywhere: Next.js caches server-side GET fetches by default
  // (the incident behind app/api/jobs/[jobId]/route.ts).
  if (path.length === 1) return relayJson(base, { cache: "no-store", headers: headers(false) });

  if (!pkg || !ID.test(pkg)) return notFound(path);

  if (path.length === 2) return relayJson(`${base}/${pkg}`, { cache: "no-store", headers: headers(false) });

  if (path.length === 3 && action === "zip") return relayFile(`${base}/${pkg}/zip`);

  if (action === "files" && FILE.test(rest.join("/"))) return relayFile(`${base}/${pkg}/files/${rest.join("/")}`);

  return notFound(path);
}

// POST /api/packages/<draft>                     -> build one ({channels})
// POST /api/packages/<draft>/<package>/wordpress -> send its post to the site, as a draft
export async function POST(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path ?? [];
  const [draft, pkg, action] = path;

  if (!draft || !ID.test(draft)) return notFound(path);

  const base = `${BACKEND_URL}/drafts/${draft}/packages`;

  if (path.length === 1) {
    const body = await request.text();
    return relayJson(base, { method: "POST", headers: headers(true), body: body || "{}" });
  }

  if (path.length === 3 && ID.test(pkg) && action === "wordpress") {
    return relayJson(`${base}/${pkg}/wordpress`, { method: "POST", headers: headers(true), body: "{}" });
  }

  return notFound(path);
}
