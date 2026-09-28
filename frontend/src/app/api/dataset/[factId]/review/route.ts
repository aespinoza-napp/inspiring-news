import { NextRequest } from "next/server";
import { forward } from "../../forward";

export async function POST(request: NextRequest, { params }: { params: { factId: string } }) {
  return forward(`/dataset/facts/${encodeURIComponent(params.factId)}/review`, {
    method: "POST",
    body: await request.json(),
  });
}
