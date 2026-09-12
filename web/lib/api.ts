import { ZodError } from "zod";
import { postgresRepository, type Repository } from "@/lib/db/repository";

export function repository(): Repository {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL не настроен");
  return postgresRepository();
}

export function jsonError(error: unknown, status = 400): Response {
  const message = error instanceof ZodError
    ? error.issues[0]?.message ?? "Проверьте заполнение полей"
    : error instanceof Error ? error.message : "Не удалось выполнить действие";
  return Response.json({ ok: false, error: message }, { status });
}

export async function body(request: Request): Promise<unknown> {
  try { return await request.json(); }
  catch { throw new Error("Ожидался JSON-запрос"); }
}
