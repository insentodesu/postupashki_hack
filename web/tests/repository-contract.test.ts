import { describe, expect, it } from "vitest";
import { MemoryRepository, attributionRows } from "@/lib/db/repository";

describe("measurement repository contract", () => {
  it("serializes attribution fields for the Postgres batch insert", () => {
    expect(attributionRows([{
      orderId: 7,
      placementId: "placement",
      attributionMethod: "deterministic",
      confidence: "deterministic",
      revenueCredit: 20_000,
      windowDays: 30,
    }])).toEqual([{
      order_id: 7,
      placement_id: "placement",
      attribution_method: "deterministic",
      confidence: "deterministic",
      revenue_credit: 20_000,
      window_days: 30,
    }]);
  });

  it("persists the complete measurement path idempotently", async () => {
    const repository = new MemoryRepository();
    await repository.createCampaign({
      campaignId: "camp",
      name: "Launch",
      objective: "Sales",
      targetCourse: "Python",
      budget: 100_000,
      startDate: null,
      endDate: null,
      notes: null,
      dataOrigin: "demo",
    });
    await repository.createPlacement({
      placementId: "placement",
      campaignId: "camp",
      channel: "@channel",
      creativeId: "creative",
      cost: 10_000,
      publicationTime: null,
      targetCourse: "Python",
      trackingToken: "p_token",
      dataOrigin: "demo",
    });
    expect((await repository.placementByToken("p_token"))?.placementId).toBe("placement");

    await repository.ensureUser("hashed-user");
    await repository.recordTouch({
      userKey: "hashed-user",
      placementId: "placement",
      source: "bot_deeplink",
      confidence: "deterministic",
      dataOrigin: "demo",
    });
    const firstLead = await repository.upsertOpenLead("hashed-user", "Python", "demo");
    const secondLead = await repository.upsertOpenLead("hashed-user", "Python", "demo");
    expect(secondLead).toBe(firstLead);

    const order = await repository.insertOrder({
      userKey: "hashed-user",
      externalId: "order-1",
      course: "Python",
      amount: 20_000,
      ts: "2026-09-12T12:00:00.000Z",
      dataOrigin: "demo",
    });
    expect(order).not.toBeNull();
    expect(await repository.insertOrder({
      userKey: "hashed-user",
      externalId: "order-1",
      course: "Python",
      amount: 20_000,
      ts: "2026-09-12T12:00:00.000Z",
      dataOrigin: "demo",
    })).toBeNull();

    const snapshot = await repository.dashboardSnapshot();
    expect(snapshot.campaigns).toHaveLength(1);
    expect(snapshot.placements).toHaveLength(1);
    expect(snapshot.touches).toHaveLength(1);
    expect(snapshot.leads).toHaveLength(1);
    expect(snapshot.orders).toHaveLength(1);
  });
});
