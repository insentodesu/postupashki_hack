import { describe, expect, it } from "vitest";
import { campaignSchema, placementSchema, simulationSchema } from "@/lib/validation";

describe("API validation", () => {
  it("rejects negative placement cost", () => {
    expect(placementSchema.safeParse({ campaignId: "c", channel: "tg", cost: -1, dataOrigin: "demo" }).success).toBe(false);
  });

  it("rejects an unknown data origin", () => {
    expect(campaignSchema.safeParse({ name: "Launch", dataOrigin: "fake" }).success).toBe(false);
  });

  it("requires placement for simulation", () => {
    expect(simulationSchema.safeParse({ amount: 20_000 }).success).toBe(false);
  });
});
