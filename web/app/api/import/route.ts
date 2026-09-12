import { requireApiSession } from "@/lib/auth/guard";
import { jsonError, repository } from "@/lib/api";
import { importSales, parseSalesWorkbook } from "@/lib/measurement/import-sales";
import { recomputeAttribution } from "@/lib/measurement/service";

export const runtime = "nodejs";
export async function POST(request: Request) {
  const denied = await requireApiSession(); if (denied) return denied;
  try {
    const file = (await request.formData()).get("file");
    if (!(file instanceof File)) throw new Error("Выберите Excel-файл");
    if (file.size > 10 * 1024 * 1024) throw new Error("Максимальный размер файла: 10 МБ");
    const repo = repository();
    const orders = await parseSalesWorkbook(await file.arrayBuffer(), process.env.USER_HASH_SECRET ?? "");
    const result = await importSales(repo, orders);
    await recomputeAttribution(repo, 30);
    return Response.json({ ok: true, ...result });
  } catch (error) { return jsonError(error); }
}
