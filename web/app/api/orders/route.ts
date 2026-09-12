import { requireApiSession } from "@/lib/auth/guard";
import { body, jsonError, repository } from "@/lib/api";
import { recomputeAttribution } from "@/lib/measurement/service";
import { orderSchema } from "@/lib/validation";

export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try {
    const input = orderSchema.parse(await body(request)); const repo = repository();
    if (input.userKey) await repo.ensureUser(input.userKey);
    const orderId = await repo.insertOrder({ ...input, userKey: input.userKey ?? null, course: input.course ?? null, externalId: `manual-${crypto.randomUUID()}`, sourceFile: null, reconstructionRule: "manual_payment", orderConfidence: "high" });
    await recomputeAttribution(repo, 30);
    return Response.json({ ok: true, orderId });
  } catch (error) { return jsonError(error); }
}
