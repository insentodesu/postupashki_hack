import { requireApiSession } from "@/lib/auth/guard";
import { body, jsonError, repository } from "@/lib/api";
import { simulateFlow } from "@/lib/measurement/service";
import { simulationSchema } from "@/lib/validation";

export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try { return Response.json({ ok: true, ...(await simulateFlow(repository(), simulationSchema.parse(await body(request)))) }); }
  catch (error) { return jsonError(error); }
}
