"""
Синтетический end-to-end tracking layer для demo/MVP.

Что создаётся:
- 1 synthetic campaign;
- 3 synthetic marketing activities с известными cost и tracking_code;
- aggregate metric snapshots для этих activities;
- 120 synthetic users с telegram_hash identities;
- 200 deterministic user-level touches;
- 84 leads;
- 50 orders + 50 order_items.

Важно:
- реальные и реконструированные записи НЕ изменяются;
- все demo-записи имеют data_origin='synthetic';
- повторный запуск удаляет только предыдущий demo-набор с префиксом
  demo202609 и создаёт его заново;
- это демонстрационный tracking flow, а не попытка восстановить
  исторические user-level touches задним числом.
"""

import hashlib
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import psycopg


DEMO_PREFIX = "demo202609"
DEMO_CAMPAIGN_KEY = f"{DEMO_PREFIX}:campaign"
N_USERS = 120
N_LEADS = 84
N_ORDERS = 50
EXPECTED_TOUCHES = 200
RANDOM_SEED = 20260912


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "postupashki"),
        user=os.getenv("POSTGRES_USER", "postupashki"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def ensure_schema(cur):
    required = [
        ("marketing_activities", "source_activity_key"),
        ("marketing_activities", "tracking_code"),
        ("touches", "tracking_method"),
        ("leads", "source_touch_id"),
        ("orders", "source_order_key"),
    ]

    for table_name, column_name in required:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = %s
            )
            """,
            (table_name, column_name),
        )
        if not cur.fetchone()[0]:
            raise RuntimeError(
                f"Не найдено поле {table_name}.{column_name}. "
                "Убедитесь, что предыдущие миграции применены."
            )


def cleanup_previous_demo(cur):
    """
    Удаляем только наш demo-набор.

    Сначала orders, потому что orders.user_id не имеет ON DELETE CASCADE.
    После этого users можно удалить, и их touches/leads уйдут каскадом.
    """
    cur.execute(
        """
        SELECT user_id
        FROM user_identities
        WHERE identity_type = 'telegram_hash'
          AND identity_value LIKE %s
        """,
        (f"{DEMO_PREFIX}:%",),
    )
    demo_user_ids = [row[0] for row in cur.fetchall()]

    if demo_user_ids:
        cur.execute(
            """
            DELETE FROM orders
            WHERE user_id = ANY(%s)
            """,
            (demo_user_ids,),
        )

        cur.execute(
            """
            DELETE FROM users
            WHERE user_id = ANY(%s)
            """,
            (demo_user_ids,),
        )

    # На случай частично завершившегося прошлого запуска.
    cur.execute(
        """
        DELETE FROM marketing_activities
        WHERE tracking_code LIKE %s
           OR source_activity_key LIKE %s
        """,
        (f"{DEMO_PREFIX}:%", f"synthetic:{DEMO_PREFIX}:%"),
    )

    cur.execute(
        """
        DELETE FROM campaigns
        WHERE campaign_key = %s
        """,
        (DEMO_CAMPAIGN_KEY,),
    )


def select_demo_courses(cur):
    """
    Берём три курса с наибольшим числом исторических order_items.

    Для synthetic single-course orders используем медиану исторического
    source_amount как ориентир масштаба цены. Это demo-генерация,
    а не утверждение о прайс-листе.
    """
    cur.execute(
        """
        SELECT
            c.course_id,
            c.course_name,
            COUNT(*) AS items_count,
            percentile_cont(0.5)
                WITHIN GROUP (ORDER BY oi.source_amount)
                AS median_source_amount
        FROM courses c
        JOIN order_items oi
            ON oi.course_id = c.course_id
        JOIN orders o
            ON o.order_id = oi.order_id
        WHERE o.data_origin <> 'synthetic'
          AND oi.source_amount IS NOT NULL
          AND oi.source_amount > 0
        GROUP BY c.course_id, c.course_name
        ORDER BY items_count DESC, c.course_id
        LIMIT 3
        """
    )
    rows = cur.fetchall()

    if len(rows) < 3:
        raise RuntimeError(
            "Для demo нужно минимум 3 курса с историческими order_items."
        )

    return [
        {
            "course_id": row[0],
            "course_name": row[1],
            "median_amount": money(row[3]),
        }
        for row in rows
    ]


def create_demo_campaign_and_activities(cur, courses, tz):
    campaign_start = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    campaign_end = datetime(2026, 9, 12, 23, 0, tzinfo=tz)

    cur.execute(
        """
        INSERT INTO campaigns (
            campaign_key,
            campaign_name,
            started_at,
            ended_at,
            description,
            data_origin
        )
        VALUES (%s, %s, %s, %s, %s, 'synthetic')
        RETURNING campaign_id
        """,
        (
            DEMO_CAMPAIGN_KEY,
            "DEMO: измеряемый запуск с deterministic tracking",
            campaign_start,
            campaign_end,
            (
                "Синтетическая demo-кампания для проверки полного "
                "measurement flow: activity → touch → lead → order."
            ),
        ),
    )
    campaign_id = cur.fetchone()[0]

    configs = [
        {
            "activity_type": "paid_telegram_ad",
            "channel_name": "Telegram Ads",
            "published_at": datetime(2026, 9, 11, 7, 30, tzinfo=tz),
            "cost": Decimal("30000.00"),
            "tracking_code": f"{DEMO_PREFIX}:tg_ads",
            "summary": "DEMO paid placement A",
            "views": 18000,
            "reposts": 45,
            "comments": 28,
            "likes": 620,
            "clicks_fwd": 820,
        },
        {
            "activity_type": "partner_placement",
            "channel_name": "Partner Telegram",
            "published_at": datetime(2026, 9, 11, 8, 0, tzinfo=tz),
            "cost": Decimal("45000.00"),
            "tracking_code": f"{DEMO_PREFIX}:partner",
            "summary": "DEMO partner placement B",
            "views": 24000,
            "reposts": 70,
            "comments": 31,
            "likes": 780,
            "clicks_fwd": 1050,
        },
        {
            "activity_type": "owned_promo",
            "channel_name": "Owned Telegram Promo",
            "published_at": datetime(2026, 9, 11, 8, 30, tzinfo=tz),
            "cost": Decimal("20000.00"),
            "tracking_code": f"{DEMO_PREFIX}:owned",
            "summary": "DEMO owned promo C",
            "views": 12500,
            "reposts": 34,
            "comments": 19,
            "likes": 510,
            "clicks_fwd": 590,
        },
    ]

    activities = []
    for idx, config in enumerate(configs):
        course = courses[idx]

        cur.execute(
            """
            INSERT INTO marketing_activities (
                campaign_id,
                course_id,
                activity_type,
                channel_name,
                published_at,
                cost,
                tracking_code,
                summary,
                source_activity_key,
                course_target_text,
                is_deleted,
                data_origin
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, 'synthetic'
            )
            RETURNING activity_id
            """,
            (
                campaign_id,
                course["course_id"],
                config["activity_type"],
                config["channel_name"],
                config["published_at"],
                config["cost"],
                config["tracking_code"],
                config["summary"],
                f"synthetic:{DEMO_PREFIX}:activity:{idx + 1}",
                course["course_name"],
            ),
        )
        activity_id = cur.fetchone()[0]

        collected_at = datetime(2026, 9, 12, 16, 0, tzinfo=tz)

        cur.execute(
            """
            INSERT INTO activity_metric_snapshots (
                activity_id,
                collected_at,
                views,
                reposts,
                comments,
                likes,
                clicks_fwd,
                data_origin
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'synthetic')
            """,
            (
                activity_id,
                collected_at,
                config["views"],
                config["reposts"],
                config["comments"],
                config["likes"],
                config["clicks_fwd"],
            ),
        )

        activities.append(
            {
                **config,
                **course,
                "activity_id": activity_id,
            }
        )

    return campaign_id, activities


def synthetic_hash(index: int) -> str:
    digest = hashlib.sha256(
        f"{DEMO_PREFIX}:telegram_numeric_id:{10_000_000 + index}".encode("utf-8")
    ).hexdigest()
    return f"{DEMO_PREFIX}:{digest}"


def create_demo_users_and_funnel(cur, activities, tz):
    rng = random.Random(RANDOM_SEED)

    all_indices = list(range(1, N_USERS + 1))
    shuffled = all_indices.copy()
    rng.shuffle(shuffled)

    lead_indices = set(shuffled[:N_LEADS])
    order_indices = set(shuffled[:N_ORDERS])

    touch_count_total = 0
    created_leads = 0
    created_orders = 0

    touch_start = datetime(2026, 9, 11, 9, 0, tzinfo=tz)

    for i in all_indices:
        # 60 users × 1 touch + 40 × 2 + 20 × 3 = 200 touches.
        if i <= 60:
            n_touches = 1
        elif i <= 100:
            n_touches = 2
        else:
            n_touches = 3

        # Для multi-touch пользователя активности не повторяются.
        chosen = rng.sample(activities, k=n_touches)

        user_created_at = touch_start + timedelta(minutes=(i - 1) * 4 - 10)

        cur.execute(
            """
            INSERT INTO users (
                created_at,
                data_origin
            )
            VALUES (%s, 'synthetic')
            RETURNING user_id
            """,
            (user_created_at,),
        )
        user_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO user_identities (
                user_id,
                identity_type,
                identity_value,
                created_at,
                data_origin
            )
            VALUES (%s, 'telegram_hash', %s, %s, 'synthetic')
            """,
            (
                user_id,
                synthetic_hash(i),
                user_created_at,
            ),
        )

        user_touch_ids = []
        user_touch_times = []

        base_touch_time = touch_start + timedelta(minutes=(i - 1) * 4)

        for touch_idx, activity in enumerate(chosen):
            touched_at = base_touch_time + timedelta(
                minutes=touch_idx * 75 + rng.randint(0, 20)
            )

            touch_type = (
                "bot_start"
                if touch_idx == 0
                else "tracking_link_click"
            )

            cur.execute(
                """
                INSERT INTO touches (
                    user_id,
                    activity_id,
                    touched_at,
                    touch_type,
                    tracking_method,
                    confidence,
                    data_origin
                )
                VALUES (
                    %s, %s, %s, %s,
                    'deterministic',
                    1.000,
                    'synthetic'
                )
                RETURNING touch_id
                """,
                (
                    user_id,
                    activity["activity_id"],
                    touched_at,
                    touch_type,
                ),
            )
            touch_id = cur.fetchone()[0]
            user_touch_ids.append(touch_id)
            user_touch_times.append(touched_at)
            touch_count_total += 1

        # Источник лида в demo = последний deterministic touch.
        last_touch_id = user_touch_ids[-1]
        last_touch_time = user_touch_times[-1]
        last_activity = chosen[-1]

        if i in lead_indices:
            lead_created_at = last_touch_time + timedelta(
                minutes=30 + rng.randint(0, 90)
            )
            status = "converted" if i in order_indices else "qualified"

            cur.execute(
                """
                INSERT INTO leads (
                    user_id,
                    course_id,
                    source_touch_id,
                    status,
                    data_origin,
                    created_at
                )
                VALUES (%s, %s, %s, %s, 'synthetic', %s)
                RETURNING lead_id
                """,
                (
                    user_id,
                    last_activity["course_id"],
                    last_touch_id,
                    status,
                    lead_created_at,
                ),
            )
            lead_id = cur.fetchone()[0]
            created_leads += 1

            if i in order_indices:
                ordered_at = lead_created_at + timedelta(
                    minutes=45 + rng.randint(0, 240)
                )

                # Небольшая deterministic вариативность вокруг исторической медианы.
                multiplier = Decimal(
                    str(rng.choice([0.90, 1.00, 1.00, 1.10]))
                )
                revenue = money(
                    last_activity["median_amount"] * multiplier
                )

                cur.execute(
                    """
                    INSERT INTO orders (
                        user_id,
                        lead_id,
                        ordered_at,
                        revenue,
                        source_order_key,
                        reconstruction_method,
                        data_origin,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        NULL,
                        'synthetic',
                        %s
                    )
                    RETURNING order_id
                    """,
                    (
                        user_id,
                        lead_id,
                        ordered_at,
                        revenue,
                        f"synthetic:{DEMO_PREFIX}:order:{i:03d}",
                        ordered_at,
                    ),
                )
                order_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO order_items (
                        order_id,
                        course_id,
                        source_amount,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        last_activity["course_id"],
                        revenue,
                        ordered_at,
                    ),
                )

                created_orders += 1

    return {
        "touches": touch_count_total,
        "leads": created_leads,
        "orders": created_orders,
    }


def validate_demo(cur):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM campaigns
        WHERE campaign_key = %s
          AND data_origin = 'synthetic'
        """,
        (DEMO_CAMPAIGN_KEY,),
    )
    campaigns = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM marketing_activities
        WHERE tracking_code LIKE %s
          AND data_origin = 'synthetic'
        """,
        (f"{DEMO_PREFIX}:%",),
    )
    activities = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM user_identities
        WHERE identity_type = 'telegram_hash'
          AND identity_value LIKE %s
          AND data_origin = 'synthetic'
        """,
        (f"{DEMO_PREFIX}:%",),
    )
    users = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM touches t
        JOIN user_identities ui
          ON ui.user_id = t.user_id
        WHERE ui.identity_type = 'telegram_hash'
          AND ui.identity_value LIKE %s
          AND t.data_origin = 'synthetic'
        """,
        (f"{DEMO_PREFIX}:%",),
    )
    touches = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM leads l
        JOIN user_identities ui
          ON ui.user_id = l.user_id
        WHERE ui.identity_type = 'telegram_hash'
          AND ui.identity_value LIKE %s
          AND l.data_origin = 'synthetic'
        """,
        (f"{DEMO_PREFIX}:%",),
    )
    leads = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE source_order_key LIKE %s
          AND data_origin = 'synthetic'
        """,
        (f"synthetic:{DEMO_PREFIX}:%",),
    )
    orders = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM order_items oi
        JOIN orders o
          ON o.order_id = oi.order_id
        WHERE o.source_order_key LIKE %s
          AND o.data_origin = 'synthetic'
        """,
        (f"synthetic:{DEMO_PREFIX}:%",),
    )
    order_items = cur.fetchone()[0]

    actual = {
        "campaigns": campaigns,
        "activities": activities,
        "users": users,
        "touches": touches,
        "leads": leads,
        "orders": orders,
        "order_items": order_items,
    }

    expected = {
        "campaigns": 1,
        "activities": 3,
        "users": N_USERS,
        "touches": EXPECTED_TOUCHES,
        "leads": N_LEADS,
        "orders": N_ORDERS,
        "order_items": N_ORDERS,
    }

    errors = {
        key: (expected[key], actual[key])
        for key in expected
        if expected[key] != actual[key]
    }

    if errors:
        raise RuntimeError(
            "Контроль synthetic demo не прошёл: "
            + ", ".join(
                f"{key}: ожидалось {exp}, в БД {act}"
                for key, (exp, act) in errors.items()
            )
        )

    return actual


def main():
    source_timezone = os.getenv("SOURCE_TIMEZONE", "Europe/Moscow")
    tz = ZoneInfo(source_timezone)

    print("[demo] Создаю synthetic deterministic tracking layer")
    print(f"[demo] SOURCE_TIMEZONE={source_timezone}")
    print(
        "[demo] Реальные/reconstructed записи не изменяются; "
        f"пересоздаётся только набор {DEMO_PREFIX}."
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_schema(cur)
            cleanup_previous_demo(cur)

            courses = select_demo_courses(cur)

            print("[demo] Курсы для synthetic demo:")
            for course in courses:
                print(
                    "  - "
                    f"{course['course_name']} "
                    f"(median source_amount={course['median_amount']})"
                )

            _, activities = create_demo_campaign_and_activities(
                cur,
                courses,
                tz,
            )

            create_demo_users_and_funnel(
                cur,
                activities,
                tz,
            )

            actual = validate_demo(cur)

    print(
        "[demo] Контроль БД: "
        + ", ".join(f"{k}={v}" for k, v in actual.items())
    )
    print("[demo] OK: synthetic tracking layer создан.")


if __name__ == "__main__":
    main()
