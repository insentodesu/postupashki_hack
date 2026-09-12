import { requireApiSession } from "@/lib/auth/guard";
import { body, jsonError, repository } from "@/lib/api";
import { createPlacement } from "@/lib/measurement/service";
import { buildDeepLink } from "@/lib/measurement/tracking";
import { placementSchema } from "@/lib/validation";

export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try {
    const input = placementSchema.parse(await body(request));
    const result = await createPlacement(repository(), input);
    return Response.json({ ok: true, ...result, deepLink: buildDeepLink(process.env.BOT_USERNAME ?? "", result.trackingToken) });
  } catch (error) { return jsonError(error); }
}
