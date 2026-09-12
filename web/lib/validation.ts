import { z } from "zod";

export const originSchema = z.enum(["real", "synthetic", "demo"]);

export const campaignSchema = z.object({
  name: z.string().trim().min(2).max(120),
  objective: z.string().trim().max(240).optional().nullable(),
  targetCourse: z.string().trim().max(120).optional().nullable(),
  budget: z.coerce.number().min(0).optional().nullable(),
  startDate: z.string().date().optional().nullable(),
  endDate: z.string().date().optional().nullable(),
  notes: z.string().trim().max(1000).optional().nullable(),
  dataOrigin: originSchema.default("real"),
});

export const placementSchema = z.object({
  campaignId: z.string().trim().min(1),
  channel: z.string().trim().min(2).max(80),
  creativeId: z.string().trim().max(120).optional().nullable(),
  cost: z.coerce.number().min(0),
  publicationTime: z.string().datetime().optional().nullable(),
  targetCourse: z.string().trim().max(120).optional().nullable(),
  dataOrigin: originSchema.default("real"),
});

export const simulationSchema = z.object({
  placementId: z.string().trim().min(1),
  amount: z.coerce.number().positive(),
  course: z.string().trim().max(120).optional().nullable(),
  dataOrigin: originSchema.default("demo"),
});

export const attributionSchema = z.object({ windowDays: z.coerce.number().int().min(1).max(365).default(30) });

export const orderSchema = z.object({
  userKey: z.string().trim().min(1).optional().nullable(),
  amount: z.coerce.number().positive(),
  course: z.string().trim().max(120).optional().nullable(),
  ts: z.string().datetime().default(() => new Date().toISOString()),
  dataOrigin: originSchema.default("real"),
});
