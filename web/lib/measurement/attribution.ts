import type { AttributionResult, MeasurementOrder, Touch } from "./types";

export function attributeOrder(
  order: MeasurementOrder,
  touches: Touch[],
  windowDays: number,
): AttributionResult | null {
  if (!order.userKey) return null;
  const paidAt = Date.parse(order.ts);
  if (!Number.isFinite(paidAt)) return null;
  const windowStart = paidAt - windowDays * 86_400_000;

  const eligible = touches
    .filter((touch) => touch.userKey === order.userKey && touch.placementId)
    .filter((touch) => {
      const touchedAt = Date.parse(touch.ts);
      return Number.isFinite(touchedAt) && touchedAt >= windowStart && touchedAt <= paidAt;
    })
    .sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts));

  const touch = eligible[0];
  if (!touch) return null;
  return {
    orderId: order.orderId,
    placementId: touch.placementId,
    attributionMethod: touch.confidence,
    confidence: touch.confidence,
    revenueCredit: order.amount,
    windowDays,
  };
}

export function attributeOrders(
  orders: MeasurementOrder[],
  touches: Touch[],
  windowDays: number,
): AttributionResult[] {
  return orders.map((order) =>
    attributeOrder(order, touches, windowDays) ?? {
      orderId: order.orderId,
      placementId: null,
      attributionMethod: "unknown",
      confidence: "unknown",
      revenueCredit: order.amount,
      windowDays,
    },
  );
}
