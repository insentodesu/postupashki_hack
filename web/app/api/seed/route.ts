import { requireApiSession } from "@/lib/auth/guard";
import { jsonError, repository } from "@/lib/api";
import { seedDemo } from "@/lib/measurement/service";

export async function POST() {
  const denied = await requireApiSession(); if (denied) return denied;
  try { return Response.json({ ok: true, ...(await seedDemo(repository())) }); }
  catch (error) { return jsonError(error); }
}
