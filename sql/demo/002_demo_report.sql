-- 009_demo_report.sql
-- One-command terminal report for the MVP defense.
-- Run:
-- docker compose exec -T db psql -U postupashki -d postupashki < sql/009_demo_report.sql

\pset pager off
\pset border 2
\pset null '[unknown]'
\pset footer on

\echo ''
\echo '=============================================================='
\echo ' POSTUPASHKI MVP — MEASUREMENT SYSTEM DEMO'
\echo '=============================================================='
\echo ''

\echo '1) DATA PROVENANCE: где реальные, reconstructed и synthetic данные'
SELECT
    dataset,
    data_origin,
    rows_count
FROM vw_data_provenance_summary
ORDER BY
    dataset,
    data_origin;

\echo ''
\echo '2) SYNTHETIC END-TO-END FUNNEL'
SELECT
    activities,
    touches,
    touched_users,
    leads,
    orders,
    buyers,
    revenue,
    touched_user_to_lead_pct AS user_to_lead_pct,
    touched_user_to_buyer_pct AS user_to_buyer_pct,
    lead_to_buyer_pct
FROM vw_demo_funnel;

\echo ''
\echo '3) MARKETING ACTIVITY DELIVERY'
SELECT
    tracking_code,
    channel_name,
    cost,
    views,
    clicks_fwd,
    total_interactions,
    interaction_rate_pct
FROM vw_marketing_activity_performance
WHERE campaign_key = 'demo202609:campaign'
ORDER BY activity_id;

\echo ''
\echo '4) ATTRIBUTION BY ACTIVITY — FIRST / LAST / LINEAR'
SELECT
    attribution_model,
    tracking_code,
    channel_name,
    cost,
    attributed_orders,
    attributed_revenue,
    ROUND(romi_attr * 100, 1) AS romi_attr_pct
FROM vw_demo_activity_scorecard
ORDER BY
    attribution_model,
    activity_id;

\echo ''
\echo '5) ATTRIBUTION QA — revenue and weights must reconcile'
SELECT
    model_name,
    COUNT(*) AS orders,
    COUNT(*) FILTER (
        WHERE NOT revenue_matches_order
    ) AS revenue_errors,
    COUNT(*) FILTER (
        WHERE NOT weight_matches_one
    ) AS weight_errors
FROM vw_attribution_order_check
WHERE order_data_origin = 'synthetic'
GROUP BY model_name
ORDER BY model_name;

\echo ''
\echo '6) ATTRIBUTION ROMI vs INCREMENTAL ROMI'
SELECT
    attribution_model,
    marketing_cost,
    attributed_revenue,
    ROUND(romi_attr * 100, 1) AS romi_attr_pct,

    observed_revenue,
    counterfactual_revenue,
    incremental_revenue,
    incremental_orders,
    ROUND(romi_inc * 100, 1) AS romi_inc_pct,

    incrementality_data_origin
FROM vw_demo_measurement_summary
ORDER BY attribution_model;

\echo ''
\echo '=============================================================='
\echo ' INTERPRETATION'
\echo ' Attribution: how occurred revenue is credited to touchpoints.'
\echo ' Incrementality: how much revenue is estimated to exist because of marketing.'
\echo ' Therefore ROMI_attr and ROMI_inc answer different questions.'
\echo ' Current incrementality estimate is SYNTHETIC demo data, not historical causal proof.'
\echo '=============================================================='
