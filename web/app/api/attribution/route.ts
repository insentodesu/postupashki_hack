import { requireApiSession } from "@/lib/auth/guard";
import { body, jsonError, repository } from "@/lib/api";
import { recomputeAttribution } from "@/lib/measurement/service";
import { attributionSchema } from "@/lib/validation";

export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try { const { windowDays } = attributionSchema.parse(await body(request)); return Response.json({ ok: true, count: (await recomputeAttribution(repository(), windowDays)).length }); }
  catch (error) { return jsonError(error); }
}
