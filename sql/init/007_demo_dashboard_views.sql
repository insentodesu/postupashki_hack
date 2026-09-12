-- 008_demo_dashboard_views.sql
-- Финальные demo-витрины для защиты MVP Postupashki.
--
-- Цель:
--   1) показать происхождение данных;
--   2) показать synthetic end-to-end funnel;
--   3) сравнить marketing activities и attribution;
--   4) рядом показать ROMI_attr и ROMI_inc.
--
-- Все demo-витрины явно фильтруют campaign_key = 'demo202609:campaign'.

BEGIN;

-- ============================================================
-- 1. DATA PROVENANCE
-- ============================================================

CREATE OR REPLACE VIEW vw_data_provenance_summary AS
SELECT
    'users'::TEXT AS dataset,
    data_origin,
    COUNT(*)::BIGINT AS rows_count
FROM users
GROUP BY data_origin

UNION ALL

SELECT
    'user_identities',
    data_origin,
    COUNT(*)::BIGINT
FROM user_identities
GROUP BY data_origin

UNION ALL

SELECT
    'campaigns',
    data_origin,
    COUNT(*)::BIGINT
FROM campaigns
GROUP BY data_origin

UNION ALL

SELECT
    'marketing_activities',
    data_origin,
    COUNT(*)::BIGINT
FROM marketing_activities
GROUP BY data_origin

UNION ALL

SELECT
    'activity_metric_snapshots',
    data_origin,
    COUNT(*)::BIGINT
FROM activity_metric_snapshots
GROUP BY data_origin

UNION ALL

SELECT
    'touches',
    data_origin,
    COUNT(*)::BIGINT
FROM touches
GROUP BY data_origin

UNION ALL

SELECT
    'leads',
    data_origin,
    COUNT(*)::BIGINT
FROM leads
GROUP BY data_origin

UNION ALL

SELECT
    'orders',
    data_origin,
    COUNT(*)::BIGINT
FROM orders
GROUP BY data_origin

UNION ALL

SELECT
    'order_items',
    o.data_origin,
    COUNT(*)::BIGINT
FROM order_items oi
JOIN orders o
  ON o.order_id = oi.order_id
GROUP BY o.data_origin

UNION ALL

SELECT
    'attributions',
    o.data_origin,
    COUNT(*)::BIGINT
FROM attributions a
JOIN orders o
  ON o.order_id = a.order_id
GROUP BY o.data_origin

UNION ALL

SELECT
    'incrementality_estimates',
    data_origin,
    COUNT(*)::BIGINT
FROM incrementality_estimates
GROUP BY data_origin;

COMMENT ON VIEW vw_data_provenance_summary IS
'QA / governance витрина: показывает объём observed, reconstructed и synthetic данных по основным слоям MVP.';


-- ============================================================
-- 2. DEMO FUNNEL
-- ============================================================

CREATE OR REPLACE VIEW vw_demo_funnel AS
WITH demo_campaign AS (
    SELECT campaign_id
    FROM campaigns
    WHERE campaign_key = 'demo202609:campaign'
),
demo_activities AS (
    SELECT ma.activity_id
    FROM marketing_activities ma
    JOIN demo_campaign dc
      ON dc.campaign_id = ma.campaign_id
    WHERE ma.data_origin = 'synthetic'
),
demo_touches AS (
    SELECT t.*
    FROM touches t
    JOIN demo_activities da
      ON da.activity_id = t.activity_id
    WHERE t.data_origin = 'synthetic'
),
demo_users AS (
    SELECT DISTINCT user_id
    FROM demo_touches
),
demo_leads AS (
    SELECT l.*
    FROM leads l
    JOIN demo_users du
      ON du.user_id = l.user_id
    WHERE l.data_origin = 'synthetic'
),
demo_orders AS (
    SELECT o.*
    FROM orders o
    JOIN demo_leads dl
      ON dl.lead_id = o.lead_id
    WHERE o.data_origin = 'synthetic'
)
SELECT
    (SELECT COUNT(*) FROM demo_activities)::BIGINT AS activities,
    (SELECT COUNT(*) FROM demo_touches)::BIGINT AS touches,
    (SELECT COUNT(*) FROM demo_users)::BIGINT AS touched_users,
    (SELECT COUNT(*) FROM demo_leads)::BIGINT AS leads,
    (
        SELECT COUNT(DISTINCT user_id)
        FROM demo_leads
    )::BIGINT AS lead_users,
    (SELECT COUNT(*) FROM demo_orders)::BIGINT AS orders,
    (
        SELECT COUNT(DISTINCT user_id)
        FROM demo_orders
    )::BIGINT AS buyers,
    COALESCE(
        (SELECT SUM(revenue) FROM demo_orders),
        0
    )::NUMERIC(14, 2) AS revenue,

    ROUND(
        100.0
        * (SELECT COUNT(DISTINCT user_id) FROM demo_leads)
        / NULLIF((SELECT COUNT(*) FROM demo_users), 0),
        2
    ) AS touched_user_to_lead_pct,

    ROUND(
        100.0
        * (SELECT COUNT(DISTINCT user_id) FROM demo_orders)
        / NULLIF((SELECT COUNT(*) FROM demo_users), 0),
        2
    ) AS touched_user_to_buyer_pct,

    ROUND(
        100.0
        * (SELECT COUNT(DISTINCT user_id) FROM demo_orders)
        / NULLIF(
            (SELECT COUNT(DISTINCT user_id) FROM demo_leads),
            0
        ),
        2
    ) AS lead_to_buyer_pct;

COMMENT ON VIEW vw_demo_funnel IS
'Synthetic demo funnel for campaign demo202609:campaign: marketing activities → touches/users → leads → orders/revenue.';


-- ============================================================
-- 3. DEMO ACTIVITY SCORECARD
-- ============================================================

CREATE OR REPLACE VIEW vw_demo_activity_scorecard AS
SELECT
    ar.model_name AS attribution_model,

    mp.activity_id,
    mp.tracking_code,
    mp.activity_type,
    mp.channel_name,
    mp.course_target_text,

    mp.cost,
    mp.views,
    mp.clicks_fwd,
    mp.total_interactions,
    mp.interaction_rate_pct,

    ar.attributed_orders,
    ar.attributed_buyers,
    ar.attributed_revenue,
    ar.romi_attr,

    mp.data_origin
FROM vw_marketing_activity_performance mp
JOIN vw_activity_romi_attr ar
  ON ar.activity_id = mp.activity_id
WHERE mp.campaign_key = 'demo202609:campaign'
  AND mp.data_origin = 'synthetic';

COMMENT ON VIEW vw_demo_activity_scorecard IS
'Activity-level demo scorecard: delivery metrics + attribution + ROMI_attr for first_touch, last_touch and linear.';


-- ============================================================
-- 4. DEMO MEASUREMENT SUMMARY
-- ============================================================

CREATE OR REPLACE VIEW vw_demo_measurement_summary AS
SELECT
    attribution_model,
    campaign_id,
    campaign_key,
    campaign_name,

    marketing_cost,

    attributed_revenue,
    romi_attr,

    incrementality_method,
    observed_revenue,
    counterfactual_revenue,
    incremental_revenue,
    incremental_orders,
    ci_lower,
    ci_upper,
    incremental_roas,
    romi_inc,

    incrementality_data_origin
FROM vw_campaign_measurement_compare
WHERE campaign_key = 'demo202609:campaign';

COMMENT ON VIEW vw_demo_measurement_summary IS
'Главная demo-витрина для защиты: attributed revenue/ROMI_attr рядом с synthetic causal incremental revenue/ROMI_inc.';

COMMIT;
