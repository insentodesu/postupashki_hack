import { describe, expect, it } from "vitest";
import { MemoryRepository } from "@/lib/db/repository";
import { importSales, normalizeSalesRows } from "@/lib/measurement/import-sales";

class CountingRepository extends MemoryRepository {
  batchCalls = 0;
  singleCalls = 0;

  override async insertOrders(orders: Parameters<MemoryRepository["insertOrders"]>[0]) {
    this.batchCalls += 1;
    return super.insertOrders(orders);
  }

  override async insertOrder(order: Parameters<MemoryRepository["insertOrder"]>[0]) {
    this.singleCalls += 1;
    return super.insertOrder(order);
  }
}

describe("Excel sales import", () => {
  it("accepts Russian headers and bundles same student and timestamp", async () => {
    const orders = await normalizeSalesRows([
      { "Номер студента": 42, "Сумма": 12000, "Курс": "Python", "Время": "2026-09-10 12:00:00" },
      { "Номер студента": 42, "Сумма": 8000, "Курс": "SQL", "Время": "2026-09-10 12:00:00" },
    ], "secret");
    expect(orders).toHaveLength(1);
    expect(orders[0]).toMatchObject({ amount: 20000, course: "Python, SQL", reconstructionRule: "same_user_same_ts_candidate_bundle", orderConfidence: "medium", dataOrigin: "real" });
    expect(orders[0].externalId).toMatch(/^excel-/);
    expect(orders[0].userKey).not.toContain("42");
  });

  it("marks a single line as high confidence", async () => {
    const [order] = await normalizeSalesRows([{ student_id: "s1", amount: 5000, course: "Math", ts: "2026-09-10T10:00:00Z" }], "secret");
    expect(order).toMatchObject({ reconstructionRule: "single_line", orderConfidence: "high" });
  });

  it("writes imported orders through one batch repository operation", async () => {
    const repository = new CountingRepository();
    const orders = await normalizeSalesRows([
      { student_id: "s1", amount: 5000, course: "Math", ts: "2026-09-10T10:00:00Z" },
      { student_id: "s2", amount: 7000, course: "Python", ts: "2026-09-10T11:00:00Z" },
    ], "secret");

    await expect(importSales(repository, orders)).resolves.toEqual({ imported: 2, skipped: 0 });
    expect(repository.batchCalls).toBe(1);
    expect(repository.singleCalls).toBe(0);
  });
});
