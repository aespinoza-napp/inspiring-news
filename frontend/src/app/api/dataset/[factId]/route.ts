import { NextRequest } from "next/server";
import { forward } from "../forward";

export async function PUT(request: NextRequest, { params }: { params: { factId: string } }) {
  return forward(`/dataset/facts/${encodeURIComponent(params.factId)}`, {
    method: "PUT",
    body: await request.json(),
  });
}

export async function DELETE(_request: NextRequest, { params }: { params: { factId: string } }) {
  return forward(`/dataset/facts/${encodeURIComponent(params.factId)}`, { method: "DELETE" });
}
