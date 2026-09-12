-- 003_views.sql
-- Аналитические представления для MVP Postupashki.
--
-- Важно:
-- 1) Order-level revenue считается только из orders.revenue.
-- 2) Course-level source_amount НЕ называется revenue, потому что в bundle-заказах
--    это исходное распределение суммы по строкам, а не гарантированная цена курса.
-- 3) Для marketing metrics берётся последний доступный snapshot каждой активности.
-- 4) Исторические cost/tracking_code могут быть NULL — это отражается как unknown,
--    а не подменяется нулём.
-- 5) Для календарного дня используется Europe/Moscow, в соответствии с рабочим
--    допущением текущих loaders для timezone-naive исходных timestamp.

BEGIN;

-- ============================================================
-- 1. Продажи по дням: честная order-level выручка
-- ============================================================

CREATE OR REPLACE VIEW vw_sales_daily AS
SELECT
    (o.ordered_at AT TIME ZONE 'Europe/Moscow')::date AS sale_date,
    COUNT(*) AS orders_count,
    COUNT(DISTINCT o.user_id) AS buyers_count,
    SUM(o.revenue)::NUMERIC(14, 2) AS revenue,
    ROUND(AVG(o.revenue), 2)::NUMERIC(14, 2) AS avg_order_value,
    COUNT(*) FILTER (WHERE o.data_origin = 'observed') AS observed_orders,
    COUNT(*) FILTER (WHERE o.data_origin = 'reconstructed') AS reconstructed_orders,
    COUNT(*) FILTER (WHERE o.data_origin = 'synthetic') AS synthetic_orders
FROM orders o
GROUP BY 1;

COMMENT ON VIEW vw_sales_daily IS
'Order-level витрина продаж по дням. revenue считается из orders.revenue и поэтому не задваивается из-за нескольких order_items в одном заказе.';

COMMENT ON COLUMN vw_sales_daily.sale_date IS
'Календарная дата продажи в Europe/Moscow согласно текущему рабочему допущению loaders.';

COMMENT ON COLUMN vw_sales_daily.revenue IS
'Сумма orders.revenue за день. Это основная историческая выручка для order-level анализа.';


-- ============================================================
-- 2. Продажи / продуктовая активность по курсам
-- ============================================================

CREATE OR REPLACE VIEW vw_course_sales AS
SELECT
    c.course_id,
    c.course_name,
    COUNT(*) AS order_item_rows,
    COUNT(DISTINCT oi.order_id) AS orders_with_course,
    COUNT(DISTINCT o.user_id) AS buyers_count,
    SUM(oi.source_amount)::NUMERIC(14, 2) AS source_amount_sum,
    ROUND(AVG(oi.source_amount), 2)::NUMERIC(14, 2) AS avg_source_amount,
    MIN(o.ordered_at) AS first_ordered_at,
    MAX(o.ordered_at) AS last_ordered_at
FROM order_items oi
JOIN orders o
    ON o.order_id = oi.order_id
JOIN courses c
    ON c.course_id = oi.course_id
GROUP BY
    c.course_id,
    c.course_name;

COMMENT ON VIEW vw_course_sales IS
'Course-level витрина. Показывает наличие курса в заказах и исходные суммы строк. source_amount_sum нельзя автоматически трактовать как истинную standalone-выручку курса при bundle-покупках.';

COMMENT ON COLUMN vw_course_sales.source_amount_sum IS
'Сумма order_items.source_amount. Сохраняет исходное распределение сумм по строкам и не называется revenue из-за bundle-неоднозначности.';


-- ============================================================
-- 3. Последнее состояние каждой marketing activity
-- ============================================================

CREATE OR REPLACE VIEW vw_marketing_activity_performance AS
WITH latest_snapshot AS (
    SELECT DISTINCT ON (s.activity_id)
        s.activity_id,
        s.snapshot_id,
        s.collected_at,
        s.views,
        s.reposts,
        s.comments,
        s.likes,
        s.clicks_fwd,
        s.data_origin AS snapshot_data_origin
    FROM activity_metric_snapshots s
    ORDER BY
        s.activity_id,
        s.collected_at DESC,
        s.snapshot_id DESC
)
SELECT
    ma.activity_id,
    ma.source_activity_key,
    ma.activity_type,
    ma.channel_name,
    ma.published_at,
    ma.course_id,
    c.course_name,
    ma.course_target_text,
    ma.discount_pct,
    ma.summary,
    ma.linked_spike,
    ma.is_deleted,

    ma.campaign_id,
    cp.campaign_key,
    cp.campaign_name,

    ma.cost,
    (ma.cost IS NOT NULL) AS has_known_cost,
    ma.tracking_code,
    (ma.tracking_code IS NOT NULL) AS has_tracking_code,

    ls.collected_at AS metrics_collected_at,
    ls.views,
    ls.reposts,
    ls.comments,
    ls.likes,
    ls.clicks_fwd,

    (
        COALESCE(ls.reposts, 0)
        + COALESCE(ls.comments, 0)
        + COALESCE(ls.likes, 0)
        + COALESCE(ls.clicks_fwd, 0)
    ) AS total_interactions,

    CASE
        WHEN ls.views > 0 THEN ROUND(
            100.0 * (
                COALESCE(ls.reposts, 0)
                + COALESCE(ls.comments, 0)
                + COALESCE(ls.likes, 0)
                + COALESCE(ls.clicks_fwd, 0)
            ) / ls.views,
            2
        )
        ELSE NULL
    END AS interaction_rate_pct,

    CASE
        WHEN ma.cost IS NOT NULL AND ls.views > 0 THEN
            ROUND((ma.cost * 1000.0 / ls.views), 2)
        ELSE NULL
    END AS cost_per_1000_views,

    ma.data_origin,
    ls.snapshot_data_origin
FROM marketing_activities ma
LEFT JOIN campaigns cp
    ON cp.campaign_id = ma.campaign_id
LEFT JOIN courses c
    ON c.course_id = ma.course_id
LEFT JOIN latest_snapshot ls
    ON ls.activity_id = ma.activity_id;

COMMENT ON VIEW vw_marketing_activity_performance IS
'Витрина одной строки на marketing activity с последним доступным snapshot метрик. Исторические cost и tracking_code могут быть NULL и не заменяются нулём.';

COMMENT ON COLUMN vw_marketing_activity_performance.interaction_rate_pct IS
'Расчётная метрика: 100 * (reposts + comments + likes + clicks_fwd) / views. Это описательная interaction rate, не causal metric.';

COMMENT ON COLUMN vw_marketing_activity_performance.cost_per_1000_views IS
'Расчётная стоимость 1000 просмотров только там, где cost известен и views > 0.';


-- ============================================================
-- 4. Агрегат marketing activities на уровне кампании
-- ============================================================

CREATE OR REPLACE VIEW vw_campaign_performance AS
WITH activity_level AS (
    SELECT *
    FROM vw_marketing_activity_performance
)
SELECT
    al.campaign_id,
    COALESCE(al.campaign_key, 'uncampaigned') AS campaign_key,
    COALESCE(al.campaign_name, 'Без кампании') AS campaign_name,

    COUNT(*) AS activities_count,
    MIN(al.published_at) AS first_activity_at,
    MAX(al.published_at) AS last_activity_at,

    COUNT(*) FILTER (
        WHERE al.metrics_collected_at IS NOT NULL
    ) AS activities_with_metrics,

    SUM(al.views) AS views,
    SUM(al.reposts) AS reposts,
    SUM(al.comments) AS comments,
    SUM(al.likes) AS likes,
    SUM(al.clicks_fwd) AS clicks_fwd,
    SUM(al.total_interactions) AS total_interactions,

    CASE
        WHEN SUM(al.views) > 0 THEN ROUND(
            100.0 * SUM(al.total_interactions) / SUM(al.views),
            2
        )
        ELSE NULL
    END AS interaction_rate_pct,

    COUNT(*) FILTER (
        WHERE al.has_known_cost
    ) AS activities_with_known_cost,

    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE al.has_known_cost)
        / NULLIF(COUNT(*), 0),
        2
    ) AS cost_coverage_pct,

    SUM(al.cost) FILTER (
        WHERE al.cost IS NOT NULL
    )::NUMERIC(14, 2) AS known_cost_sum,

    CASE
        WHEN COUNT(*) FILTER (WHERE al.cost IS NOT NULL) = COUNT(*)
        THEN SUM(al.cost)::NUMERIC(14, 2)
        ELSE NULL
    END AS total_cost_complete,

    COUNT(*) FILTER (
        WHERE al.has_tracking_code
    ) AS activities_with_tracking_code,

    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE al.has_tracking_code)
        / NULLIF(COUNT(*), 0),
        2
    ) AS tracking_coverage_pct

FROM activity_level al
GROUP BY
    al.campaign_id,
    COALESCE(al.campaign_key, 'uncampaigned'),
    COALESCE(al.campaign_name, 'Без кампании');

COMMENT ON VIEW vw_campaign_performance IS
'Campaign-level агрегат по marketing activities на основе последних snapshots. unknown cost не считается нулевым; total_cost_complete заполняется только при 100% cost coverage.';

COMMENT ON COLUMN vw_campaign_performance.known_cost_sum IS
'Сумма только известных cost. Если часть cost неизвестна, это не полная стоимость кампании.';

COMMENT ON COLUMN vw_campaign_performance.total_cost_complete IS
'Полная стоимость кампании только если cost известен у каждой activity; иначе NULL.';

COMMENT ON COLUMN vw_campaign_performance.tracking_coverage_pct IS
'Доля marketing activities с tracking_code. Для исторических реконструированных публикаций ожидаемо может быть 0%.';

COMMIT;
