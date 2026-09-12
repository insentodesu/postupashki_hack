import { databasePool } from "./client";
import type {
  AttributionResult,
  Campaign,
  Confidence,
  DashboardSnapshot,
  DataOrigin,
  Lead,
  MeasurementOrder,
  Placement,
  Touch,
} from "@/lib/measurement/types";

export type CampaignInput = Omit<Campaign, "createdAt">;
export type PlacementInput = Omit<Placement, "createdAt">;
export type TouchInput = Omit<Touch, "touchId" | "ts"> & { ts?: string };
export type OrderInput = Omit<MeasurementOrder, "orderId">;

export interface Repository {
  createCampaign(input: CampaignInput): Promise<void>;
  createPlacement(input: PlacementInput): Promise<void>;
  placementByToken(token: string): Promise<Placement | null>;
  placementById(id: string): Promise<Placement | null>;
  ensureUser(userKey: string): Promise<void>;
  recordTouch(input: TouchInput): Promise<number>;
  latestTouch(userKey: string): Promise<Touch | null>;
  upsertOpenLead(userKey: string, course: string | null, origin: DataOrigin): Promise<number>;
  insertOrder(input: OrderInput): Promise<number | null>;
  insertOrders(inputs: OrderInput[]): Promise<{ imported: number; skipped: number }>;
  replaceAttributions(items: AttributionResult[]): Promise<void>;
  dashboardSnapshot(): Promise<DashboardSnapshot>;
  claimTelegramUpdate(updateId: number): Promise<boolean>;
}

const now = () => new Date().toISOString();

export class MemoryRepository implements Repository {
  private campaigns: Campaign[] = [];
  private placements: Placement[] = [];
  private users = new Set<string>();
  private touches: Touch[] = [];
  private leads: Lead[] = [];
  private orders: MeasurementOrder[] = [];
  private attributions: AttributionResult[] = [];
  private updates = new Set<number>();

  async createCampaign(input: CampaignInput) {
    if (this.campaigns.some((row) => row.campaignId === input.campaignId)) {
      throw new Error("Кампания с таким ID уже существует");
    }
    this.campaigns.push({ ...input, createdAt: now() });
  }

  async createPlacement(input: PlacementInput) {
    if (!this.campaigns.some((row) => row.campaignId === input.campaignId)) {
      throw new Error("Кампания не найдена");
    }
    if (this.placements.some((row) => row.trackingToken === input.trackingToken)) {
      throw new Error("Tracking token уже используется");
    }
    this.placements.push({ ...input, createdAt: now() });
  }

  async placementByToken(token: string) {
    return this.placements.find((row) => row.trackingToken === token) ?? null;
  }

  async placementById(id: string) {
    return this.placements.find((row) => row.placementId === id) ?? null;
  }

  async ensureUser(userKey: string) { this.users.add(userKey); }

  async recordTouch(input: TouchInput) {
    const touchId = this.touches.length + 1;
    this.touches.push({ ...input, touchId, ts: input.ts ?? now() });
    return touchId;
  }

  async latestTouch(userKey: string) {
    return this.touches
      .filter((row) => row.userKey === userKey)
      .sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))[0] ?? null;
  }

  async upsertOpenLead(userKey: string, course: string | null, dataOrigin: DataOrigin) {
    const existing = this.leads.find(
      (row) => row.userKey === userKey && row.course === course && row.status === "new",
    );
    if (existing) return existing.leadId;
    const leadId = this.leads.length + 1;
    this.leads.push({ leadId, userKey, course, status: "new", dataOrigin, createdAt: now() });
    return leadId;
  }

  async insertOrder(input: OrderInput) {
    if (input.externalId && this.orders.some((row) => row.externalId === input.externalId)) {
      return null;
    }
    const orderId = this.orders.length + 1;
    this.orders.push({ ...input, orderId });
    return orderId;
  }

  async insertOrders(inputs: OrderInput[]) {
    let imported = 0;
    let skipped = 0;
    for (const input of inputs) {
      if (input.userKey) this.users.add(input.userKey);
      if (input.externalId && this.orders.some((row) => row.externalId === input.externalId)) {
        skipped += 1;
        continue;
      }
      const orderId = this.orders.length + 1;
      this.orders.push({ ...input, orderId });
      imported += 1;
    }
    return { imported, skipped };
  }

  async replaceAttributions(items: AttributionResult[]) { this.attributions = [...items]; }

  async dashboardSnapshot(): Promise<DashboardSnapshot> {
    return {
      campaigns: [...this.campaigns],
      placements: [...this.placements],
      touches: [...this.touches],
      leads: [...this.leads],
      orders: [...this.orders],
      attributions: [...this.attributions],
    };
  }

  async claimTelegramUpdate(updateId: number) {
    if (this.updates.has(updateId)) return false;
    this.updates.add(updateId);
    return true;
  }
}

type DbRow = Record<string, unknown>;
const text = (value: unknown) => value == null ? null : String(value);
const number = (value: unknown) => Number(value ?? 0);
const timestamp = (value: unknown) => value instanceof Date ? value.toISOString() : String(value);

function campaign(row: DbRow): Campaign {
  return {
    campaignId: String(row.campaign_id), name: String(row.name), objective: text(row.objective),
    targetCourse: text(row.target_course), budget: row.budget == null ? null : number(row.budget),
    startDate: text(row.start_date), endDate: text(row.end_date), notes: text(row.notes),
    dataOrigin: String(row.data_origin) as DataOrigin, createdAt: timestamp(row.created_at),
  };
}

function placement(row: DbRow): Placement {
  return {
    placementId: String(row.placement_id), campaignId: String(row.campaign_id),
    channel: String(row.channel), creativeId: text(row.creative_id), cost: number(row.cost),
    publicationTime: row.publication_time == null ? null : timestamp(row.publication_time),
    targetCourse: text(row.target_course), trackingToken: String(row.tracking_token),
    dataOrigin: String(row.data_origin) as DataOrigin, createdAt: timestamp(row.created_at),
  };
}

function touch(row: DbRow): Touch {
  return {
    touchId: number(row.touch_id), userKey: String(row.user_key), placementId: text(row.placement_id),
    ts: timestamp(row.ts), source: String(row.source), confidence: String(row.confidence) as Confidence,
    dataOrigin: String(row.data_origin) as DataOrigin,
  };
}

function lead(row: DbRow): Lead {
  return {
    leadId: number(row.lead_id), userKey: String(row.user_key), course: text(row.course),
    createdAt: timestamp(row.created_at), status: String(row.status),
    dataOrigin: String(row.data_origin) as DataOrigin,
  };
}

function order(row: DbRow): MeasurementOrder {
  return {
    orderId: number(row.order_id), userKey: text(row.user_key), externalId: text(row.external_id),
    course: text(row.course), amount: number(row.amount), ts: timestamp(row.ts),
    sourceFile: text(row.source_file), reconstructionRule: text(row.order_reconstruction_rule),
    orderConfidence: text(row.order_confidence), dataOrigin: String(row.data_origin) as DataOrigin,
  };
}

function attribution(row: DbRow): AttributionResult {
  return {
    orderId: number(row.order_id), placementId: text(row.placement_id),
    attributionMethod: String(row.attribution_method) as Confidence,
    confidence: String(row.confidence) as Confidence, revenueCredit: number(row.revenue_credit),
    windowDays: number(row.window_days),
  };
}

export function postgresRepository(): Repository {
  const pool = databasePool();
  return {
    async createCampaign(input) {
      await pool.query(
        `INSERT INTO campaigns (campaign_id,name,objective,target_course,budget,start_date,end_date,notes,data_origin)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [input.campaignId, input.name, input.objective, input.targetCourse, input.budget,
          input.startDate, input.endDate, input.notes, input.dataOrigin],
      );
    },
    async createPlacement(input) {
      await pool.query(
        `INSERT INTO placements (placement_id,campaign_id,channel,creative_id,cost,publication_time,target_course,tracking_token,data_origin)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [input.placementId, input.campaignId, input.channel, input.creativeId, input.cost,
          input.publicationTime, input.targetCourse, input.trackingToken, input.dataOrigin],
      );
    },
    async placementByToken(token) {
      const result = await pool.query("SELECT * FROM placements WHERE tracking_token=$1", [token]);
      return result.rows[0] ? placement(result.rows[0] as DbRow) : null;
    },
    async placementById(id) {
      const result = await pool.query("SELECT * FROM placements WHERE placement_id=$1", [id]);
      return result.rows[0] ? placement(result.rows[0] as DbRow) : null;
    },
    async ensureUser(userKey) {
      await pool.query("INSERT INTO users (user_key) VALUES ($1) ON CONFLICT DO NOTHING", [userKey]);
    },
    async recordTouch(input) {
      const result = await pool.query(
        `INSERT INTO touches (user_key,placement_id,ts,source,confidence,data_origin)
         VALUES ($1,$2,COALESCE($3::timestamptz,now()),$4,$5,$6) RETURNING touch_id`,
        [input.userKey, input.placementId, input.ts ?? null, input.source, input.confidence, input.dataOrigin],
      );
      return number(result.rows[0].touch_id);
    },
    async latestTouch(userKey) {
      const result = await pool.query("SELECT * FROM touches WHERE user_key=$1 ORDER BY ts DESC LIMIT 1", [userKey]);
      return result.rows[0] ? touch(result.rows[0] as DbRow) : null;
    },
    async upsertOpenLead(userKey, course, origin) {
      const result = await pool.query(
        `INSERT INTO leads (user_key,course,data_origin) VALUES ($1,$2,$3)
         ON CONFLICT (user_key, (COALESCE(course, ''))) WHERE status='new'
         DO UPDATE SET user_key=EXCLUDED.user_key RETURNING lead_id`,
        [userKey, course, origin],
      );
      return number(result.rows[0].lead_id);
    },
    async insertOrder(input) {
      const result = await pool.query(
        `INSERT INTO orders (user_key,external_id,course,amount,ts,source_file,order_reconstruction_rule,order_confidence,data_origin)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
         ON CONFLICT (external_id) DO NOTHING RETURNING order_id`,
        [input.userKey, input.externalId ?? null, input.course, input.amount, input.ts,
          input.sourceFile ?? null, input.reconstructionRule ?? null, input.orderConfidence ?? null,
          input.dataOrigin],
      );
      return result.rows[0] ? number(result.rows[0].order_id) : null;
    },
    async insertOrders(inputs) {
      if (!inputs.length) return { imported: 0, skipped: 0 };
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        const userKeys = [...new Set(inputs.flatMap((input) => input.userKey ? [input.userKey] : []))];
        if (userKeys.length) {
          await client.query(
            `INSERT INTO users (user_key)
             SELECT user_key FROM unnest($1::text[]) AS input(user_key)
             ON CONFLICT DO NOTHING`,
            [userKeys],
          );
        }
        const rows = inputs.map((input) => ({
          user_key: input.userKey,
          external_id: input.externalId ?? null,
          course: input.course,
          amount: input.amount,
          ts: input.ts,
          source_file: input.sourceFile ?? null,
          order_reconstruction_rule: input.reconstructionRule ?? null,
          order_confidence: input.orderConfidence ?? null,
          data_origin: input.dataOrigin,
        }));
        const result = await client.query(
          `INSERT INTO orders (user_key,external_id,course,amount,ts,source_file,order_reconstruction_rule,order_confidence,data_origin)
           SELECT user_key,external_id,course,amount,ts,source_file,order_reconstruction_rule,order_confidence,data_origin
           FROM jsonb_to_recordset($1::jsonb) AS imported(
             user_key text, external_id text, course text, amount numeric, ts timestamptz,
             source_file text, order_reconstruction_rule text, order_confidence text, data_origin text
           )
           ON CONFLICT (external_id) DO NOTHING
           RETURNING order_id`,
          [JSON.stringify(rows)],
        );
        await client.query("COMMIT");
        const imported = result.rows.length;
        return { imported, skipped: inputs.length - imported };
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      } finally {
        client.release();
      }
    },
    async replaceAttributions(items) {
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        await client.query("DELETE FROM attributions");
        await client.query(
          `INSERT INTO attributions (order_id,placement_id,attribution_method,confidence,revenue_credit,window_days)
           SELECT order_id,placement_id,attribution_method,confidence,revenue_credit,window_days
           FROM jsonb_to_recordset($1::jsonb) AS attribution(
             order_id bigint, placement_id text, attribution_method text, confidence text,
             revenue_credit numeric, window_days integer
           )`,
          [JSON.stringify(items)],
        );
        await client.query("COMMIT");
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      } finally {
        client.release();
      }
    },
    async dashboardSnapshot() {
      const [campaigns, placements, touches, leads, orders, attributions] = await Promise.all([
        pool.query("SELECT * FROM campaigns ORDER BY created_at DESC"),
        pool.query("SELECT * FROM placements ORDER BY created_at DESC"),
        pool.query("SELECT * FROM touches ORDER BY ts DESC"),
        pool.query("SELECT * FROM leads ORDER BY created_at DESC"),
        pool.query("SELECT * FROM orders ORDER BY ts DESC"),
        pool.query("SELECT * FROM attributions ORDER BY computed_at DESC"),
      ]);
      return {
        campaigns: campaigns.rows.map((row) => campaign(row as DbRow)),
        placements: placements.rows.map((row) => placement(row as DbRow)),
        touches: touches.rows.map((row) => touch(row as DbRow)),
        leads: leads.rows.map((row) => lead(row as DbRow)),
        orders: orders.rows.map((row) => order(row as DbRow)),
        attributions: attributions.rows.map((row) => attribution(row as DbRow)),
      };
    },
    async claimTelegramUpdate(updateId) {
      const result = await pool.query(
        "INSERT INTO telegram_updates (update_id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING update_id",
        [updateId],
      );
      return Boolean(result.rows[0]);
    },
  };
}
