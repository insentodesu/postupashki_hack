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
    const botUsername = process.env.BOT_USERNAME?.trim();
    if (!botUsername) throw new Error("BOT_USERNAME не задан");
    return Response.json({ ok: true, ...result, deepLink: buildDeepLink(botUsername, result.trackingToken) });
  } catch (error) { return jsonError(error); }
}
