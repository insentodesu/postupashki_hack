import { describe, expect, it } from "vitest";
import { attributeOrder } from "@/lib/measurement/attribution";
import { calculateRomi } from "@/lib/measurement/romi";
import { buildDeepLink, hashTelegramId } from "@/lib/measurement/tracking";
import type { MeasurementOrder, Touch } from "@/lib/measurement/types";

const paidAt = "2026-09-12T12:00:00.000Z";
const order: MeasurementOrder = {
  orderId: 1,
  userKey: "user-a",
  amount: 20_000,
  course: "Python",
  ts: paidAt,
  dataOrigin: "demo",
};

const touches: Touch[] = [
  {
    touchId: 1,
    userKey: "user-a",
    placementId: "first",
    ts: "2026-09-10T12:00:00.000Z",
    source: "bot_deeplink",
    confidence: "deterministic",
    dataOrigin: "demo",
  },
  {
    touchId: 2,
    userKey: "user-a",
    placementId: "last",
    ts: "2026-09-11T12:00:00.000Z",
    source: "bot_deeplink",
    confidence: "deterministic",
    dataOrigin: "demo",
  },
  {
    touchId: 3,
    userKey: "user-a",
    placementId: "future",
    ts: "2026-09-12T12:01:00.000Z",
    source: "bot_deeplink",
    confidence: "deterministic",
    dataOrigin: "demo",
  },
];

describe("measurement rules", () => {
  it("selects the latest eligible touch before payment", () => {
    expect(attributeOrder(order, touches, 30)?.placementId).toBe("last");
  });

  it("ignores touches outside the attribution window", () => {
    const old = [{ ...touches[0], ts: "2026-08-01T12:00:00.000Z" }];
    expect(attributeOrder(order, old, 30)).toBeNull();
  });

  it("keeps an untracked order unknown", () => {
    expect(attributeOrder({ ...order, userKey: null }, touches, 30)).toBeNull();
  });

  it("calculates revenue ROMI and returns N/A for zero spend", () => {
    expect(calculateRomi(20_000, 10_000)).toBe(1);
    expect(calculateRomi(20_000, 0)).toBeNull();
  });

  it("hashes Telegram IDs deterministically without exposing the raw ID", async () => {
    const first = await hashTelegramId("123456789", "test-secret");
    const second = await hashTelegramId(123456789, "test-secret");
    expect(first).toBe(second);
    expect(first).not.toContain("123456789");
    expect(first).toHaveLength(32);
  });

  it("builds a clean environment-backed Telegram deep link", () => {
    expect(buildDeepLink("@postupashki_bot", "p_abc")).toBe(
      "https://t.me/postupashki_bot?start=p_abc",
    );
  });
});
