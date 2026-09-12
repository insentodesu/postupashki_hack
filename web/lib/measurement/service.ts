import type { Repository } from "@/lib/db/repository";
import { attributeOrders } from "./attribution";
import { newTrackingToken } from "./tracking";
import type { DataOrigin } from "./types";

export async function recomputeAttribution(repo: Repository, windowDays = 30) {
  const snapshot = await repo.dashboardSnapshot();
  const results = attributeOrders(snapshot.orders, snapshot.touches, windowDays);
  await repo.replaceAttributions(results);
  return results;
}

export async function createCampaign(repo: Repository, input: {
  name: string; objective?: string | null; targetCourse?: string | null; budget?: number | null;
  startDate?: string | null; endDate?: string | null; notes?: string | null; dataOrigin: DataOrigin;
}) {
  const campaignId = `cmp_${crypto.randomUUID().slice(0, 8)}`;
  await repo.createCampaign({ campaignId, name: input.name, objective: input.objective ?? null,
    targetCourse: input.targetCourse ?? null, budget: input.budget ?? null,
    startDate: input.startDate ?? null, endDate: input.endDate ?? null, notes: input.notes ?? null,
    dataOrigin: input.dataOrigin });
  return campaignId;
}

export async function createPlacement(repo: Repository, input: {
  campaignId: string; channel: string; creativeId?: string | null; cost: number;
  publicationTime?: string | null; targetCourse?: string | null; dataOrigin: DataOrigin;
}) {
  const placementId = `plc_${crypto.randomUUID().slice(0, 8)}`;
  const trackingToken = newTrackingToken();
  await repo.createPlacement({ placementId, campaignId: input.campaignId, channel: input.channel,
    creativeId: input.creativeId ?? null, cost: input.cost, publicationTime: input.publicationTime ?? null,
    targetCourse: input.targetCourse ?? null, trackingToken, dataOrigin: input.dataOrigin });
  return { placementId, trackingToken };
}

export async function simulateFlow(repo: Repository, input: {
  placementId: string; amount: number; course?: string | null; dataOrigin: DataOrigin;
}) {
  const placement = await repo.placementById(input.placementId);
  if (!placement) throw new Error("Размещение не найдено");
  const userKey = `sim_${crypto.randomUUID().replaceAll("-", "").slice(0, 16)}`;
  await repo.ensureUser(userKey);
  await repo.recordTouch({ userKey, placementId: placement.placementId, source: "offline_simulation",
    confidence: "deterministic", dataOrigin: input.dataOrigin });
  await repo.upsertOpenLead(userKey, input.course ?? placement.targetCourse, input.dataOrigin);
  const orderId = await repo.insertOrder({ userKey, externalId: `sim-order-${crypto.randomUUID()}`,
    course: input.course ?? placement.targetCourse, amount: input.amount, ts: new Date().toISOString(),
    sourceFile: null, reconstructionRule: "simulation", orderConfidence: "high", dataOrigin: input.dataOrigin });
  await recomputeAttribution(repo, 30);
  return { userKey, orderId };
}

export async function seedDemo(repo: Repository) {
  const snapshot = await repo.dashboardSnapshot();
  if (snapshot.campaigns.some((item) => item.campaignId === "demo-launch")) return { seeded: false };
  await repo.createCampaign({ campaignId: "demo-launch", name: "Осенний набор", objective: "Проверить окупаемость каналов", targetCourse: "Python-разработчик", budget: 25000, startDate: null, endDate: null, notes: "Демонстрационный набор", dataOrigin: "demo" });
  await repo.createPlacement({ placementId: "demo-tg", campaignId: "demo-launch", channel: "Telegram", creativeId: "tg-01", cost: 10000, publicationTime: null, targetCourse: "Python-разработчик", trackingToken: "demo_python", dataOrigin: "demo" });
  await repo.createPlacement({ placementId: "demo-vk", campaignId: "demo-launch", channel: "VK", creativeId: "vk-01", cost: 15000, publicationTime: null, targetCourse: "Аналитик данных", trackingToken: "demo_analytics", dataOrigin: "demo" });
  const paidAt = new Date(); const touchAt = new Date(paidAt.valueOf() - 3_600_000).toISOString();
  for (const [userKey, placementId, confidence, amount] of [
    ["demo-user-1", "demo-tg", "deterministic", 20000],
    ["demo-user-2", "demo-tg", "deterministic", 14000],
    ["demo-user-3", "demo-vk", "self_reported", 18000],
  ] as const) {
    await repo.ensureUser(userKey);
    await repo.recordTouch({ userKey, placementId, source: confidence === "deterministic" ? "telegram_deeplink" : "survey", confidence, dataOrigin: "demo", ts: touchAt });
    await repo.upsertOpenLead(userKey, "Python-разработчик", "demo");
    await repo.insertOrder({ userKey, externalId: `seed-${userKey}`, course: "Python-разработчик", amount, ts: paidAt.toISOString(), sourceFile: null, reconstructionRule: "demo_seed", orderConfidence: "high", dataOrigin: "demo" });
  }
  await repo.insertOrder({ userKey: null, externalId: "seed-unknown", course: "Python-разработчик", amount: 12000, ts: paidAt.toISOString(), sourceFile: null, reconstructionRule: "demo_seed", orderConfidence: "high", dataOrigin: "demo" });
  await recomputeAttribution(repo, 30);
  return { seeded: true };
}
