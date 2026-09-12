import { describe, expect, it, vi } from "vitest";
import { MemoryRepository } from "@/lib/db/repository";
import { handleTelegramUpdate } from "@/lib/telegram";

describe("Telegram webhook", () => {
  it("turns a valid /start into a deterministic touch without storing raw id", async () => {
    const repo = new MemoryRepository();
    await repo.createCampaign({ campaignId: "c1", name: "Test", objective: null, targetCourse: "Python", budget: null, startDate: null, endDate: null, notes: null, dataOrigin: "demo" });
    await repo.createPlacement({ placementId: "p1", campaignId: "c1", channel: "Telegram", creativeId: null, cost: 10000, publicationTime: null, targetCourse: "Python", trackingToken: "token", dataOrigin: "demo" });
    const send = vi.fn(async () => undefined);
    await handleTelegramUpdate({ update_id: 1, message: { chat: { id: 123456789 }, from: { id: 123456789 }, text: "/start token" } }, repo, { token: "bot", userSecret: "secret" }, send);
    const snapshot = await repo.dashboardSnapshot();
    expect(snapshot.touches[0]).toMatchObject({ placementId: "p1", confidence: "deterministic" });
    expect(JSON.stringify(snapshot)).not.toContain("123456789");
  });

  it("deduplicates repeat CTA leads", async () => {
    const repo = new MemoryRepository();
    const send = vi.fn(async () => undefined);
    const update = { update_id: 2, callback_query: { id: "q", from: { id: 7 }, message: { chat: { id: 7 } }, data: "course" } };
    await handleTelegramUpdate(update, repo, { token: "bot", userSecret: "secret" }, send);
    await handleTelegramUpdate({ ...update, update_id: 3 }, repo, { token: "bot", userSecret: "secret" }, send);
    expect((await repo.dashboardSnapshot()).leads).toHaveLength(1);
  });
});
