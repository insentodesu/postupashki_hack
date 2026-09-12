import readXlsxFile from "read-excel-file/node";
import type { OrderInput, Repository } from "@/lib/db/repository";
import { hashTelegramId } from "./tracking";

type RawRow = Record<string, unknown>;
const aliases = {
  studentId: ["student_id", "student id", "номер студента"],
  amount: ["amount", "сумма"],
  course: ["course", "курс"],
  ts: ["ts", "timestamp", "time", "время"],
} as const;

function cleanKey(value: unknown) { return String(value ?? "").trim().toLowerCase(); }
function pick(row: RawRow, names: readonly string[]) {
  const entry = Object.entries(row).find(([key]) => names.includes(cleanKey(key)));
  return entry?.[1];
}

function isoTime(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "number") return new Date(Math.round((value - 25569) * 86400 * 1000)).toISOString();
  const normalized = String(value ?? "").trim().replace(" ", "T");
  const parsed = new Date(normalized);
  if (!normalized || Number.isNaN(parsed.valueOf())) throw new Error(`Некорректное время оплаты: ${String(value)}`);
  return parsed.toISOString();
}

async function shortDigest(value: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes)).map((byte) => byte.toString(16).padStart(2, "0")).join("").slice(0, 24);
}

export async function normalizeSalesRows(rows: RawRow[], secret: string): Promise<OrderInput[]> {
  if (!secret) throw new Error("USER_HASH_SECRET не настроен");
  const groups = new Map<string, { studentId: string; ts: string; amounts: number[]; courses: string[] }>();
  for (const row of rows) {
    const studentId = String(pick(row, aliases.studentId) ?? "").trim();
    const amount = Number(pick(row, aliases.amount));
    const ts = isoTime(pick(row, aliases.ts));
    const course = String(pick(row, aliases.course) ?? "").trim();
    if (!studentId) throw new Error("В файле отсутствует номер студента");
    if (!Number.isFinite(amount) || amount <= 0) throw new Error("Сумма должна быть положительным числом");
    const key = `${studentId}\u0000${ts}`;
    const current = groups.get(key) ?? { studentId, ts, amounts: [], courses: [] };
    current.amounts.push(amount);
    if (course && !current.courses.includes(course)) current.courses.push(course);
    groups.set(key, current);
  }
  return Promise.all(Array.from(groups.values()).map(async (group) => ({
    userKey: `student_${await hashTelegramId(group.studentId, secret)}`,
    externalId: `excel-${await shortDigest(`${group.studentId}|${group.ts}`)}`,
    course: group.courses.join(", ") || null,
    amount: group.amounts.reduce((sum, item) => sum + item, 0),
    ts: group.ts,
    sourceFile: "excel-upload",
    reconstructionRule: group.amounts.length === 1 ? "single_line" : "same_user_same_ts_candidate_bundle",
    orderConfidence: group.amounts.length === 1 ? "high" : "medium",
    dataOrigin: "real" as const,
  })));
}

export async function parseSalesWorkbook(buffer: ArrayBuffer, secret: string) {
  const cells = await readXlsxFile(Buffer.from(buffer));
  if (!cells.length) throw new Error("Excel-файл не содержит строк");
  const headers = cells[0].map(String);
  const rows = cells.slice(1).map((values) => Object.fromEntries(headers.map((header, column) => [header, values[column]])))
    .filter((item) => Object.values(item).some((value) => value != null && value !== ""));
  return normalizeSalesRows(rows, secret);
}

export async function importSales(repo: Repository, orders: OrderInput[]) {
  let imported = 0; let skipped = 0;
  for (const order of orders) {
    if (order.userKey) await repo.ensureUser(order.userKey);
    const id = await repo.insertOrder(order);
    if (id == null) skipped += 1; else imported += 1;
  }
  return { imported, skipped };
}
