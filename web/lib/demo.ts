import type { DashboardSnapshot } from "@/lib/measurement/types";

export const demoSnapshot: DashboardSnapshot = {
  campaigns: [{ campaignId: "demo-launch", name: "Осенний набор", objective: "Проверить окупаемость каналов", targetCourse: "Python-разработчик", budget: 25000, startDate: null, endDate: null, notes: null, dataOrigin: "demo", createdAt: "2026-09-10T09:00:00Z" }],
  placements: [
    { placementId: "demo-tg", campaignId: "demo-launch", channel: "Telegram", creativeId: "tg-01", cost: 10000, publicationTime: "2026-09-10T09:00:00Z", targetCourse: "Python-разработчик", trackingToken: "demo_python", dataOrigin: "demo", createdAt: "2026-09-10T09:00:00Z" },
    { placementId: "demo-vk", campaignId: "demo-launch", channel: "VK", creativeId: "vk-01", cost: 15000, publicationTime: "2026-09-10T09:00:00Z", targetCourse: "Аналитик данных", trackingToken: "demo_analytics", dataOrigin: "demo", createdAt: "2026-09-10T09:00:00Z" },
  ],
  touches: [
    { touchId: 1, userKey: "8f4…2da", placementId: "demo-tg", ts: "2026-09-10T10:12:00Z", source: "telegram_deeplink", confidence: "deterministic", dataOrigin: "demo" },
    { touchId: 2, userKey: "c91…eb7", placementId: "demo-tg", ts: "2026-09-10T10:23:00Z", source: "telegram_deeplink", confidence: "deterministic", dataOrigin: "demo" },
    { touchId: 3, userKey: "51a…dda", placementId: "demo-vk", ts: "2026-09-10T11:02:00Z", source: "survey", confidence: "self_reported", dataOrigin: "demo" },
  ],
  leads: [
    { leadId: 1, userKey: "8f4…2da", course: "Python-разработчик", createdAt: "2026-09-10T10:15:00Z", status: "new", dataOrigin: "demo" },
    { leadId: 2, userKey: "c91…eb7", course: "Python-разработчик", createdAt: "2026-09-10T10:25:00Z", status: "new", dataOrigin: "demo" },
    { leadId: 3, userKey: "51a…dda", course: "Аналитик данных", createdAt: "2026-09-10T11:05:00Z", status: "new", dataOrigin: "demo" },
  ],
  orders: [
    { orderId: 1, userKey: "8f4…2da", externalId: "demo-1", course: "Python-разработчик", amount: 20000, ts: "2026-09-10T13:00:00Z", dataOrigin: "demo" },
    { orderId: 2, userKey: "c91…eb7", externalId: "demo-2", course: "Python-разработчик", amount: 14000, ts: "2026-09-10T14:00:00Z", dataOrigin: "demo" },
    { orderId: 3, userKey: "51a…dda", externalId: "demo-3", course: "Аналитик данных", amount: 18000, ts: "2026-09-10T15:00:00Z", dataOrigin: "demo" },
    { orderId: 4, userKey: null, externalId: "demo-4", course: "Python-разработчик", amount: 12000, ts: "2026-09-10T16:00:00Z", dataOrigin: "demo" },
  ],
  attributions: [
    { orderId: 1, placementId: "demo-tg", attributionMethod: "deterministic", confidence: "deterministic", revenueCredit: 20000, windowDays: 30 },
    { orderId: 2, placementId: "demo-tg", attributionMethod: "deterministic", confidence: "deterministic", revenueCredit: 14000, windowDays: 30 },
    { orderId: 3, placementId: "demo-vk", attributionMethod: "self_reported", confidence: "self_reported", revenueCredit: 18000, windowDays: 30 },
    { orderId: 4, placementId: null, attributionMethod: "unknown", confidence: "unknown", revenueCredit: 12000, windowDays: 30 },
  ],
};
