import { NextRequest } from "next/server";
import { forward } from "./forward";

export async function GET() {
  return forward("/dataset", { method: "GET" });
}

export async function POST(request: NextRequest) {
  return forward("/dataset/facts", { method: "POST", body: await request.json() });
}
