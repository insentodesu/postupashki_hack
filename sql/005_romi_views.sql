-- 005_romi_views.sql
-- QA attribution + attributed ROMI views.
--
-- ROMI_attr = (Attributed Revenue - Marketing Cost) / Marketing Cost
--
-- Важно:
-- это attribution ROMI, НЕ incrementality / causal ROMI.
-- Unknown cost не считается нулём.

BEGIN;


-- ============================================================
-- 1. QA: сходится ли attribution по каждому заказу и модели
-- ============================================================

CREATE OR REPLACE VIEW vw_attribution_order_check AS
SELECT
    a.model_name,
    o.order_id,
    o.data_origin AS order_data_origin,
    o.revenue AS order_revenue,
    COUNT(*) AS attributed_touches,
    SUM(a.attribution_weight)::NUMERIC(12, 5) AS weight_sum,
    SUM(a.attributed_revenue)::NUMERIC(14, 2) AS attributed_revenue_sum,
    (
        SUM(a.attributed_revenue) = o.revenue
    ) AS revenue_matches_order,
    (
        ABS(SUM(a.attribution_weight) - 1.0) < 0.00001
    ) AS weight_matches_one
FROM attributions a
JOIN orders o
  ON o.order_id = a.order_id
GROUP BY
    a.model_name,
    o.order_id,
    o.data_origin,
    o.revenue;

COMMENT ON VIEW vw_attribution_order_check IS
'QA-витрина: проверяет, что attributed revenue по каждой модели сходится с revenue заказа и веса дают 1.';


-- ============================================================
-- 2. Attribution + ROMI на уровне marketing activity
-- ============================================================

CREATE OR REPLACE VIEW vw_activity_romi_attr AS
WITH models(model_name) AS (
    VALUES
        ('first_touch'),
        ('last_touch'),
        ('linear')
),
activity_attr AS (
    SELECT
        a.model_name,
        t.activity_id,
        COUNT(DISTINCT a.order_id) AS attributed_orders,
        COUNT(DISTINCT t.user_id) AS attributed_buyers,
        SUM(a.attributed_revenue)::NUMERIC(14, 2) AS attributed_revenue
    FROM attributions a
    JOIN touches t
      ON t.touch_id = a.touch_id
    GROUP BY
        a.model_name,
        t.activity_id
)
SELECT
    m.model_name,
    ma.activity_id,
    ma.source_activity_key,
    ma.activity_type,
    ma.channel_name,
    ma.published_at,
    ma.campaign_id,
    c.campaign_key,
    c.campaign_name,
    ma.course_target_text,
    ma.cost,
    (ma.cost IS NOT NULL) AS has_known_cost,

    COALESCE(aa.attributed_orders, 0) AS attributed_orders,
    COALESCE(aa.attributed_buyers, 0) AS attributed_buyers,
    COALESCE(aa.attributed_revenue, 0)::NUMERIC(14, 2) AS attributed_revenue,

    CASE
        WHEN ma.cost IS NOT NULL AND ma.cost > 0 THEN
            ROUND(
                (
                    COALESCE(aa.attributed_revenue, 0) - ma.cost
                ) / ma.cost,
                4
            )
        ELSE NULL
    END AS romi_attr,

    ma.data_origin
FROM marketing_activities ma
CROSS JOIN models m
LEFT JOIN activity_attr aa
  ON aa.activity_id = ma.activity_id
 AND aa.model_name = m.model_name
LEFT JOIN campaigns c
  ON c.campaign_id = ma.campaign_id;

COMMENT ON VIEW vw_activity_romi_attr IS
'Attributed performance по marketing activity для first_touch, last_touch и linear. ROMI_attr основан на attributed revenue и не является causal/incremental ROMI.';


-- ============================================================
-- 3. Attribution + ROMI на уровне кампании
-- ============================================================

CREATE OR REPLACE VIEW vw_campaign_romi_attr AS
WITH activity_level AS (
    SELECT *
    FROM vw_activity_romi_attr
)
SELECT
    model_name,
    campaign_id,
    COALESCE(campaign_key, 'uncampaigned') AS campaign_key,
    COALESCE(campaign_name, 'Без кампании') AS campaign_name,

    COUNT(*) AS activities_count,
    SUM(attributed_orders) AS attributed_orders_activity_sum,
    SUM(attributed_revenue)::NUMERIC(14, 2) AS attributed_revenue,

    COUNT(*) FILTER (
        WHERE has_known_cost
    ) AS activities_with_known_cost,

    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE has_known_cost)
        / NULLIF(COUNT(*), 0),
        2
    ) AS cost_coverage_pct,

    SUM(cost) FILTER (
        WHERE cost IS NOT NULL
    )::NUMERIC(14, 2) AS known_cost_sum,

    CASE
        WHEN COUNT(*) FILTER (WHERE cost IS NOT NULL) = COUNT(*)
        THEN SUM(cost)::NUMERIC(14, 2)
        ELSE NULL
    END AS total_cost_complete,

    CASE
        WHEN COUNT(*) FILTER (WHERE cost IS NOT NULL) = COUNT(*)
         AND SUM(cost) > 0
        THEN ROUND(
            (
                SUM(attributed_revenue) - SUM(cost)
            ) / SUM(cost),
            4
        )
        ELSE NULL
    END AS romi_attr

FROM activity_level
GROUP BY
    model_name,
    campaign_id,
    COALESCE(campaign_key, 'uncampaigned'),
    COALESCE(campaign_name, 'Без кампании');

COMMENT ON VIEW vw_campaign_romi_attr IS
'Campaign-level attributed ROMI. ROMI считается только при 100% cost coverage. Не интерпретировать как incremental/causal effect.';

COMMIT;
