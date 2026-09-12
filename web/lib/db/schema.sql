CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id text PRIMARY KEY,
  name text NOT NULL,
  objective text,
  target_course text,
  budget numeric(14,2),
  start_date date,
  end_date date,
  notes text,
  data_origin text NOT NULL CHECK (data_origin IN ('real', 'synthetic', 'demo')),
  created_at timestamptz NOT NULL DEFAULT now()
);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS placements (
  placement_id text PRIMARY KEY,
  campaign_id text NOT NULL REFERENCES campaigns(campaign_id),
  channel text NOT NULL,
  creative_id text,
  cost numeric(14,2) NOT NULL DEFAULT 0,
  publication_time timestamptz,
  target_course text,
  tracking_token text UNIQUE NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('real', 'synthetic', 'demo')),
  created_at timestamptz NOT NULL DEFAULT now()
);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS users (
  user_key text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS touches (
  touch_id bigserial PRIMARY KEY,
  user_key text NOT NULL REFERENCES users(user_key),
  placement_id text REFERENCES placements(placement_id),
  ts timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  confidence text NOT NULL CHECK (confidence IN ('deterministic', 'self_reported', 'modelled', 'unknown')),
  data_origin text NOT NULL CHECK (data_origin IN ('real', 'synthetic', 'demo'))
);
-- statement-breakpoint
CREATE INDEX IF NOT EXISTS touches_user_ts_idx ON touches(user_key, ts DESC);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS leads (
  lead_id bigserial PRIMARY KEY,
  user_key text NOT NULL REFERENCES users(user_key),
  course text,
  created_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'new',
  data_origin text NOT NULL CHECK (data_origin IN ('real', 'synthetic', 'demo'))
);
-- statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS leads_open_unique_idx
  ON leads(user_key, COALESCE(course, '')) WHERE status = 'new';
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS orders (
  order_id bigserial PRIMARY KEY,
  user_key text REFERENCES users(user_key),
  external_id text UNIQUE,
  course text,
  amount numeric(14,2) NOT NULL,
  ts timestamptz NOT NULL,
  source_file text,
  order_reconstruction_rule text,
  order_confidence text,
  data_origin text NOT NULL CHECK (data_origin IN ('real', 'synthetic', 'demo'))
);
-- statement-breakpoint
CREATE INDEX IF NOT EXISTS orders_user_ts_idx ON orders(user_key, ts DESC);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS attributions (
  attribution_id bigserial PRIMARY KEY,
  order_id bigint UNIQUE NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  placement_id text REFERENCES placements(placement_id),
  attribution_method text NOT NULL,
  confidence text NOT NULL,
  revenue_credit numeric(14,2) NOT NULL,
  window_days integer NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now()
);
-- statement-breakpoint
CREATE TABLE IF NOT EXISTS telegram_updates (
  update_id bigint PRIMARY KEY,
  processed_at timestamptz NOT NULL DEFAULT now()
);
