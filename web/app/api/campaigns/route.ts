import { requireApiSession } from "@/lib/auth/guard";
import { body, jsonError, repository } from "@/lib/api";
import { createCampaign } from "@/lib/measurement/service";
import { campaignSchema } from "@/lib/validation";

export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try { const input = campaignSchema.parse(await body(request)); return Response.json({ ok: true, campaignId: await createCampaign(repository(), input) }); }
  catch (error) { return jsonError(error); }
}
