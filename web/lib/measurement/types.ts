export type DataOrigin = "real" | "synthetic" | "demo";
export type Confidence = "deterministic" | "self_reported" | "modelled" | "unknown";

export interface Campaign {
  campaignId: string;
  name: string;
  objective: string | null;
  targetCourse: string | null;
  budget: number | null;
  startDate: string | null;
  endDate: string | null;
  notes: string | null;
  dataOrigin: DataOrigin;
  createdAt: string;
}

export interface Placement {
  placementId: string;
  campaignId: string;
  channel: string;
  creativeId: string | null;
  cost: number;
  publicationTime: string | null;
  targetCourse: string | null;
  trackingToken: string;
  dataOrigin: DataOrigin;
  createdAt: string;
}

export interface Touch {
  touchId: number;
  userKey: string;
  placementId: string | null;
  ts: string;
  source: string;
  confidence: Confidence;
  dataOrigin: DataOrigin;
}

export interface Lead {
  leadId: number;
  userKey: string;
  course: string | null;
  createdAt: string;
  status: string;
  dataOrigin: DataOrigin;
}

export interface MeasurementOrder {
  orderId: number;
  userKey: string | null;
  externalId?: string | null;
  course: string | null;
  amount: number;
  ts: string;
  sourceFile?: string | null;
  reconstructionRule?: string | null;
  orderConfidence?: string | null;
  dataOrigin: DataOrigin;
}

export interface AttributionResult {
  orderId: number;
  placementId: string | null;
  attributionMethod: Confidence;
  confidence: Confidence;
  revenueCredit: number;
  windowDays: number;
}

export interface RomiRow {
  placementId: string;
  channel: string;
  dataOrigin: DataOrigin;
  spend: number;
  conversions: number;
  attributedRevenue: number;
  cac: number | null;
  romi: number | null;
  confidenceMix: Partial<Record<Confidence, number>>;
}

export interface DashboardSnapshot {
  campaigns: Campaign[];
  placements: Placement[];
  touches: Touch[];
  leads: Lead[];
  orders: MeasurementOrder[];
  attributions: AttributionResult[];
}
