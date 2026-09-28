import { forward } from "../forward";

export async function GET() {
  return forward("/dataset/review", { method: "GET" });
}
