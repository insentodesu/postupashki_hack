import { describe, expect, it } from "vitest";
import { createSessionToken, passwordMatches, verifySession } from "@/lib/auth/session";

describe("dashboard session", () => {
  it("accepts a valid token and rejects tampering", async () => {
    const token = await createSessionToken("session-secret", Date.now() + 60_000);
    expect(await verifySession(token, "session-secret")).toBe(true);
    expect(await verifySession(`${token}x`, "session-secret")).toBe(false);
  });

  it("rejects an expired token", async () => {
    const token = await createSessionToken("session-secret", Date.now() - 1);
    expect(await verifySession(token, "session-secret")).toBe(false);
  });

  it("compares the configured password without early exit", async () => {
    expect(await passwordMatches("correct", "correct")).toBe(true);
    expect(await passwordMatches("wrong", "correct")).toBe(false);
  });
});
