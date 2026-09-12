-- 006_seed_incrementality_demo.sql
-- Synthetic incrementality estimate for the demo campaign.
--
-- IMPORTANT:
-- This is NOT inferred from the historical Postupashki data.
-- It is a clearly synthetic holdout-style result used only to demonstrate
-- how a future causal measurement layer would be stored and consumed.
--
-- Demo assumption:
--   observed revenue      = actual revenue of synthetic demo orders
--   counterfactual revenue = 68% of observed revenue
--   incremental revenue    = observed - counterfactual = 32%
--   incremental orders     = round(32% of observed demo orders)
--   illustrative CI        = [20%, 44%] of observed revenue
--
-- All inserted rows are marked data_origin = 'synthetic'.

BEGIN;

-- Idempotency: remove only the previous synthetic estimate for this demo campaign.
DELETE FROM incrementality_estimates ie
USING campaigns c
WHERE ie.campaign_id = c.campaign_id
  AND c.campaign_key = 'demo202609:campaign'
  AND ie.data_origin = 'synthetic'
  AND ie.method = 'holdout';

WITH demo_campaign AS (
    SELECT campaign_id
    FROM campaigns
    WHERE campaign_key = 'demo202609:campaign'
      AND data_origin = 'synthetic'
),
demo_orders AS (
    SELECT
        COUNT(*)::INTEGER AS observed_orders,
        SUM(revenue)::NUMERIC(14, 2) AS observed_revenue
    FROM orders
    WHERE source_order_key LIKE 'synthetic:demo202609:%'
      AND data_origin = 'synthetic'
),
prepared AS (
    SELECT
        dc.campaign_id,
        d.observed_orders,
        d.observed_revenue,
        ROUND(d.observed_revenue * 0.68, 2)::NUMERIC(14, 2) AS counterfactual_revenue,
        (
            d.observed_revenue
            - ROUND(d.observed_revenue * 0.68, 2)
        )::NUMERIC(14, 2) AS incremental_revenue,
        ROUND(d.observed_orders * 0.32)::INTEGER AS incremental_orders,
        ROUND(d.observed_revenue * 0.20, 2)::NUMERIC(14, 2) AS ci_lower,
        ROUND(d.observed_revenue * 0.44, 2)::NUMERIC(14, 2) AS ci_upper
    FROM demo_campaign dc
    CROSS JOIN demo_orders d
    WHERE d.observed_orders = 50
      AND d.observed_revenue IS NOT NULL
)
INSERT INTO incrementality_estimates (
    campaign_id,
    activity_id,
    method,
    observed_revenue,
    counterfactual_revenue,
    incremental_revenue,
    incremental_orders,
    ci_lower,
    ci_upper,
    data_origin,
    estimated_at
)
SELECT
    campaign_id,
    NULL,
    'holdout',
    observed_revenue,
    counterfactual_revenue,
    incremental_revenue,
    incremental_orders,
    ci_lower,
    ci_upper,
    'synthetic',
    NOW()
FROM prepared;

DO $$
DECLARE
    estimate_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO estimate_count
    FROM incrementality_estimates ie
    JOIN campaigns c
      ON c.campaign_id = ie.campaign_id
    WHERE c.campaign_key = 'demo202609:campaign'
      AND ie.data_origin = 'synthetic'
      AND ie.method = 'holdout';

    IF estimate_count <> 1 THEN
        RAISE EXCEPTION
            'Synthetic incrementality seed failed: expected 1 estimate, got %',
            estimate_count;
    END IF;
END $$;

COMMIT;
