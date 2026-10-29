import { NextRequest, NextResponse } from "next/server";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const UNREACHABLE = `Could not reach the backend at ${BACKEND_URL}.`;

// Reader accounts (backend src/api/account_routes.py), and only these
// paths, each with its one method: anything else is a 404 here, never a
// request to the backend.
const ROUTES: Record<string, "GET" | "POST"> = {
  register: "POST",
  login: "POST",
  logout: "POST",
  password: "POST",
  delete: "POST",
  me: "GET",
  export: "GET",
};

// The session cookie, and no other: whatever else the browser holds for
// this site has no business reaching the backend.
const SESSION_COOKIE = "in_session";

// What the backend needs of the browser's request: the session, the CSRF
// token or the header that marks our own pages (sign-in), and who the
// visitor is for the per-client limits. The storage key too when this
// server has one, read here and never shipped to the browser.
function headers(request: NextRequest, json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;
  const session = request.cookies.get(SESSION_COOKIE)?.value;
  const csrf = request.headers.get("x-csrf-token");
  const ours = request.headers.get("x-requested-with");
  const forwarded = request.headers.get("x-forwarded-for");

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
    ...(session ? { Cookie: `${SESSION_COOKIE}=${session}` } : {}),
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    ...(ours ? { "X-Requested-With": ours } : {}),
    ...(forwarded ? { "X-Forwarded-For": forwarded } : {}),
  };
}

async function relay(request: NextRequest, path: string, method: "GET" | "POST") {
  if (ROUTES[path] !== method) {
    return NextResponse.json({ error: `Unknown account endpoint: ${method} ${path}` }, { status: 404 });
  }

  let response: Response;

  try {
    // no-store: an account's answers are never to be cached, here or by
    // Next.js's Data Cache (the incident in app/api/jobs/[jobId]/route.ts).
    response = await fetch(`${BACKEND_URL}/account/${path}`, {
      method,
      cache: "no-store",
      headers: headers(request, method === "POST"),
      ...(method === "POST" ? { body: (await request.text()) || "{}" } : {}),
    });
  } catch {
    return NextResponse.json({ error: UNREACHABLE }, { status: 502 });
  }

  const relayed = new NextResponse(response.status === 204 ? null : await response.text(), { status: response.status });

  // Set one by one: test_api_key.py reads every `headers:` in a proxy as
  // a request's, which must come from headers().
  for (const cookie of response.headers.getSetCookie()) relayed.headers.append("Set-Cookie", cookie);
  for (const name of ["content-type", "content-disposition", "retry-after"]) {
    const value = response.headers.get(name);
    if (value) relayed.headers.set(name, value);
  }
  relayed.headers.set("Cache-Control", "no-store");

  return relayed;
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return relay(request, params.path.join("/"), "GET");
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return relay(request, params.path.join("/"), "POST");
}
