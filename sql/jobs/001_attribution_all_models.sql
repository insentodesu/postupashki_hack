-- 004_attribution.sql
-- Пересчёт attribution для всех заказов, у которых есть user-level touches
-- в течение 30 дней до момента заказа.
--
-- Модели:
--   first_touch
--   last_touch
--   linear
--
-- Исторические reconstructed orders без touches НЕ получают фиктивную атрибуцию.

BEGIN;

-- Attribution — производный слой, поэтому эти модели пересчитываются полностью.
DELETE FROM attributions
WHERE model_name IN ('first_touch', 'last_touch', 'linear');


-- ============================================================
-- FIRST TOUCH
-- ============================================================

WITH eligible_touches AS (
    SELECT
        o.order_id,
        o.revenue,
        t.touch_id,
        t.touched_at,
        ROW_NUMBER() OVER (
            PARTITION BY o.order_id
            ORDER BY t.touched_at ASC, t.touch_id ASC
        ) AS rn
    FROM orders o
    JOIN touches t
      ON t.user_id = o.user_id
    WHERE t.touched_at <= o.ordered_at
      AND t.touched_at >= o.ordered_at - INTERVAL '30 days'
)
INSERT INTO attributions (
    order_id,
    touch_id,
    model_name,
    attribution_weight,
    attributed_revenue,
    attribution_window_days,
    calculated_at
)
SELECT
    order_id,
    touch_id,
    'first_touch',
    1.00000,
    revenue,
    30,
    NOW()
FROM eligible_touches
WHERE rn = 1;


-- ============================================================
-- LAST TOUCH
-- ============================================================

WITH eligible_touches AS (
    SELECT
        o.order_id,
        o.revenue,
        t.touch_id,
        t.touched_at,
        ROW_NUMBER() OVER (
            PARTITION BY o.order_id
            ORDER BY t.touched_at DESC, t.touch_id DESC
        ) AS rn
    FROM orders o
    JOIN touches t
      ON t.user_id = o.user_id
    WHERE t.touched_at <= o.ordered_at
      AND t.touched_at >= o.ordered_at - INTERVAL '30 days'
)
INSERT INTO attributions (
    order_id,
    touch_id,
    model_name,
    attribution_weight,
    attributed_revenue,
    attribution_window_days,
    calculated_at
)
SELECT
    order_id,
    touch_id,
    'last_touch',
    1.00000,
    revenue,
    30,
    NOW()
FROM eligible_touches
WHERE rn = 1;


-- ============================================================
-- LINEAR
-- ============================================================
-- Revenue делится поровну между eligible touches.
-- Остаток от округления до копеек добавляется последнему touch,
-- поэтому сумма attributed_revenue по заказу точно равна order revenue.

WITH eligible_touches AS (
    SELECT
        o.order_id,
        o.revenue,
        t.touch_id,
        t.touched_at,
        ROW_NUMBER() OVER (
            PARTITION BY o.order_id
            ORDER BY t.touched_at ASC, t.touch_id ASC
        ) AS rn,
        COUNT(*) OVER (
            PARTITION BY o.order_id
        ) AS touch_count
    FROM orders o
    JOIN touches t
      ON t.user_id = o.user_id
    WHERE t.touched_at <= o.ordered_at
      AND t.touched_at >= o.ordered_at - INTERVAL '30 days'
),
linear_split AS (
    SELECT
        order_id,
        touch_id,
        rn,
        touch_count,
        revenue,
        CASE
            WHEN rn < touch_count THEN
                ROUND(revenue / touch_count, 2)
            ELSE
                revenue
                - ROUND(revenue / touch_count, 2) * (touch_count - 1)
        END AS attributed_revenue,
        CASE
            WHEN rn < touch_count THEN
                ROUND(1.0 / touch_count, 5)
            ELSE
                1.0
                - ROUND(1.0 / touch_count, 5) * (touch_count - 1)
        END AS attribution_weight
    FROM eligible_touches
)
INSERT INTO attributions (
    order_id,
    touch_id,
    model_name,
    attribution_weight,
    attributed_revenue,
    attribution_window_days,
    calculated_at
)
SELECT
    order_id,
    touch_id,
    'linear',
    attribution_weight,
    attributed_revenue,
    30,
    NOW()
FROM linear_split;

COMMIT;
