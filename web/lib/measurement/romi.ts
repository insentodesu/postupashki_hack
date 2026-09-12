import type { AttributionResult, MeasurementOrder, Placement, RomiRow } from "./types";

export function calculateRomi(revenue: number, spend: number): number | null {
  return spend === 0 ? null : (revenue - spend) / spend;
}

export function buildRomiRows(
  placements: Placement[],
  attributions: AttributionResult[],
): RomiRow[] {
  return placements.map((placement) => {
    const matched = attributions.filter(
      (item) => item.placementId === placement.placementId,
    );
    const revenue = matched.reduce((sum, item) => sum + item.revenueCredit, 0);
    const confidenceMix = matched.reduce<RomiRow["confidenceMix"]>((mix, item) => {
      mix[item.confidence] = (mix[item.confidence] ?? 0) + 1;
      return mix;
    }, {});
    return {
      placementId: placement.placementId,
      channel: placement.channel,
      dataOrigin: placement.dataOrigin,
      spend: placement.cost,
      conversions: new Set(matched.map((item) => item.orderId)).size,
      attributedRevenue: revenue,
      cac: matched.length ? placement.cost / matched.length : null,
      romi: calculateRomi(revenue, placement.cost),
      confidenceMix,
    };
  });
}

export function unknownRevenue(
  orders: MeasurementOrder[],
  attributions: AttributionResult[],
): number {
  const unknownIds = new Set(
    attributions.filter((item) => !item.placementId).map((item) => item.orderId),
  );
  return orders
    .filter((order) => unknownIds.has(order.orderId))
    .reduce((sum, order) => sum + order.amount, 0);
}
