-- Application compatibility fields for the existing Streamlit UI.
BEGIN;

-- Organic/unknown touches have no marketing activity. Keep the relationship
-- nullable so a Telegram /start without a valid placement is still recorded
-- without inventing an advertising source.
ALTER TABLE touches
    ALTER COLUMN activity_id DROP NOT NULL;

ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS objective TEXT,
    ADD COLUMN IF NOT EXISTS target_course_text TEXT,
    ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2)
        CHECK (budget IS NULL OR budget >= 0),
    ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE marketing_activities
    ADD COLUMN IF NOT EXISTS creative_id TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS external_order_id TEXT,
    ADD COLUMN IF NOT EXISTS source_file TEXT,
    ADD COLUMN IF NOT EXISTS order_confidence TEXT;

CREATE INDEX IF NOT EXISTS idx_orders_external_order_id
    ON orders(external_order_id)
    WHERE external_order_id IS NOT NULL;

COMMENT ON COLUMN campaigns.objective IS
'UI metadata: stated campaign objective such as Awareness, Traffic, Leads or Sales.';
COMMENT ON COLUMN campaigns.target_course_text IS
'UI-level free-text target course; kept separate from exact course FK matching.';
COMMENT ON COLUMN campaigns.budget IS
'Planned campaign budget entered in Ad Registry.';
COMMENT ON COLUMN campaigns.notes IS
'Free-form campaign notes from the UI.';
COMMENT ON COLUMN marketing_activities.creative_id IS
'Creative identifier used by the Ad Registry UI.';
COMMENT ON COLUMN orders.external_order_id IS
'External/payment-system order identifier when available.';
COMMENT ON COLUMN orders.source_file IS
'Source file for imported orders, e.g. base.xlsx.';
COMMENT ON COLUMN orders.order_confidence IS
'Human-readable confidence of historical order reconstruction.';

COMMIT;
