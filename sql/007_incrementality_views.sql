-- 007_incrementality_views.sql
-- Incrementality / causal ROMI views.
--
-- ROMI_inc = (Incremental Revenue - Marketing Cost) / Marketing Cost
--
-- Unlike attribution ROMI, this uses incremental revenue from a causal estimate.
-- For the current demo, the estimate itself is synthetic and is marked as such.

BEGIN;

-- ============================================================
-- 1. General incrementality + ROMI view
--    Supports both campaign-level and activity-level estimates.
-- ============================================================

CREATE OR REPLACE VIEW vw_incrementality_romi AS
WITH campaign_costs AS (
    SELECT
        c.campaign_id,
        COUNT(ma.activity_id) AS activities_count,
        COUNT(ma.activity_id) FILTER (
            WHERE ma.cost IS NOT NULL
        ) AS activities_with_known_cost,
        SUM(ma.cost) FILTER (
            WHERE ma.cost IS NOT NULL
        )::NUMERIC(14, 2) AS known_cost_sum,
        CASE
            WHEN COUNT(ma.activity_id) > 0
             AND COUNT(ma.activity_id) FILTER (
                    WHERE ma.cost IS NOT NULL
                 ) = COUNT(ma.activity_id)
            THEN SUM(ma.cost)::NUMERIC(14, 2)
            ELSE NULL
        END AS total_cost_complete
    FROM campaigns c
    LEFT JOIN marketing_activities ma
      ON ma.campaign_id = c.campaign_id
    GROUP BY c.campaign_id
)
SELECT
    ie.estimate_id,
    CASE
        WHEN ie.campaign_id IS NOT NULL THEN 'campaign'
        ELSE 'activity'
    END AS scope_type,

    ie.campaign_id,
    c.campaign_key,
    c.campaign_name,

    ie.activity_id,
    ma.source_activity_key,
    ma.activity_type,
    ma.channel_name,

    ie.method,
    ie.observed_revenue,
    ie.counterfactual_revenue,
    ie.incremental_revenue,
    ie.incremental_orders,
    ie.ci_lower,
    ie.ci_upper,

    CASE
        WHEN ie.campaign_id IS NOT NULL THEN cc.known_cost_sum
        ELSE ma.cost
    END AS known_cost_sum,

    CASE
        WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
        ELSE ma.cost
    END AS total_cost_complete,

    CASE
        WHEN ie.campaign_id IS NOT NULL THEN
            ROUND(
                100.0
                * cc.activities_with_known_cost
                / NULLIF(cc.activities_count, 0),
                2
            )
        WHEN ma.cost IS NOT NULL THEN 100.00
        ELSE 0.00
    END AS cost_coverage_pct,

    CASE
        WHEN (
            CASE
                WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
                ELSE ma.cost
            END
        ) > 0
        THEN ROUND(
            ie.incremental_revenue
            /
            (
                CASE
                    WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
                    ELSE ma.cost
                END
            ),
            4
        )
        ELSE NULL
    END AS incremental_roas,

    CASE
        WHEN (
            CASE
                WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
                ELSE ma.cost
            END
        ) > 0
        THEN ROUND(
            (
                ie.incremental_revenue
                -
                (
                    CASE
                        WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
                        ELSE ma.cost
                    END
                )
            )
            /
            (
                CASE
                    WHEN ie.campaign_id IS NOT NULL THEN cc.total_cost_complete
                    ELSE ma.cost
                END
            ),
            4
        )
        ELSE NULL
    END AS romi_inc,

    ie.data_origin,
    ie.estimated_at

FROM incrementality_estimates ie
LEFT JOIN campaigns c
  ON c.campaign_id = ie.campaign_id
LEFT JOIN marketing_activities ma
  ON ma.activity_id = ie.activity_id
LEFT JOIN campaign_costs cc
  ON cc.campaign_id = ie.campaign_id;

COMMENT ON VIEW vw_incrementality_romi IS
'Incrementality / causal ROMI view. ROMI_inc uses incremental_revenue rather than attributed revenue. Current demo estimates can be synthetic and must be filtered/interpreted by data_origin.';

COMMENT ON COLUMN vw_incrementality_romi.romi_inc IS
'(incremental_revenue - complete marketing cost) / complete marketing cost. NULL when complete cost is unavailable.';

COMMENT ON COLUMN vw_incrementality_romi.incremental_roas IS
'incremental_revenue / complete marketing cost.';


-- ============================================================
-- 2. Side-by-side campaign comparison:
--    attribution ROMI vs incrementality ROMI
-- ============================================================

CREATE OR REPLACE VIEW vw_campaign_measurement_compare AS
SELECT
    ar.model_name AS attribution_model,
    ar.campaign_id,
    ar.campaign_key,
    ar.campaign_name,

    ar.attributed_revenue,
    ar.total_cost_complete AS marketing_cost,
    ar.romi_attr,

    ir.method AS incrementality_method,
    ir.observed_revenue,
    ir.counterfactual_revenue,
    ir.incremental_revenue,
    ir.incremental_orders,
    ir.ci_lower,
    ir.ci_upper,
    ir.incremental_roas,
    ir.romi_inc,

    ir.data_origin AS incrementality_data_origin

FROM vw_campaign_romi_attr ar
LEFT JOIN vw_incrementality_romi ir
  ON ir.scope_type = 'campaign'
 AND ir.campaign_id = ar.campaign_id;

COMMENT ON VIEW vw_campaign_measurement_compare IS
'Side-by-side comparison of attributed ROMI and incremental ROMI at campaign level. Attribution explains credit allocation; incrementality estimates causal lift. These metrics answer different questions.';

COMMIT;
