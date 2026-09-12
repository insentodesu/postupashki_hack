from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row


DEFAULT_TZ = ZoneInfo(os.getenv("SOURCE_TIMEZONE", "Europe/Moscow"))

_CONFIDENCE_SCORE = {
    "deterministic": Decimal("1.000"),
    "self_reported": Decimal("0.700"),
    "modelled": Decimal("0.400"),
    "unknown": Decimal("0.000"),
}


def get_conn():
    """PostgreSQL connection used by the application data adapter."""
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "postupashki"),
        user=os.getenv("POSTGRES_USER", "postupashki"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
        row_factory=dict_row,
    )


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _to_dt(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    elif value is None:
        dt = datetime.now(timezone.utc)
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.combine(date.fromisoformat(s), time.min)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def init_db():
    """
    PostgreSQL schema is created by sql/init/*.

    App startup only verifies that the schema exists; it does not silently
    create/alter production tables.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.campaigns') AS table_name")
        row = cur.fetchone()
        if not row or row["table_name"] is None:
            raise RuntimeError(
                "PostgreSQL schema is not initialized. "
                "Run Docker Compose with sql/init mounted into "
                "/docker-entrypoint-initdb.d or apply the migrations manually."
            )


def _ensure_course(cur, course_name: str | None):
    if not course_name:
        return None
    name = str(course_name).strip()
    if not name:
        return None
    cur.execute(
        """
        INSERT INTO courses (course_name)
        VALUES (%s)
        ON CONFLICT (course_name)
        DO UPDATE SET course_name = EXCLUDED.course_name
        RETURNING course_id
        """,
        (name,),
    )
    return cur.fetchone()["course_id"]


def _resolve_campaign_id(cur, campaign_key: str):
    cur.execute(
        "SELECT campaign_id FROM campaigns WHERE campaign_key = %s",
        (campaign_key,),
    )
    row = cur.fetchone()
    if not row:
        raise KeyError(f"Campaign not found: {campaign_key}")
    return row["campaign_id"]


def _resolve_activity_id(cur, placement_id: str):
    cur.execute(
        """
        SELECT activity_id
        FROM marketing_activities
        WHERE source_activity_key = %s
        """,
        (placement_id,),
    )
    row = cur.fetchone()
    if not row:
        raise KeyError(f"Placement/activity not found: {placement_id}")
    return row["activity_id"]


def _resolve_user_id(
    cur,
    user_key: str,
    *,
    create: bool = False,
    data_origin: str = "observed",
):
    cur.execute(
        """
        SELECT user_id
        FROM user_identities
        WHERE identity_type = 'telegram_hash'
          AND identity_value = %s
        """,
        (user_key,),
    )
    row = cur.fetchone()
    if row:
        return row["user_id"]

    if not create:
        return None

    cur.execute(
        """
        INSERT INTO users (data_origin)
        VALUES (%s)
        RETURNING user_id
        """,
        (data_origin,),
    )
    user_id = cur.fetchone()["user_id"]

    cur.execute(
        """
        INSERT INTO user_identities (
            user_id,
            identity_type,
            identity_value,
            data_origin
        )
        VALUES (%s, 'telegram_hash', %s, %s)
        """,
        (user_id, user_key, data_origin),
    )
    return user_id


def _identity_sql(alias: str = "u"):
    # Prefer telegram_hash for the live product; otherwise show any available ID.
    return f"""
    COALESCE(
        (
            SELECT ui.identity_value
            FROM user_identities ui
            WHERE ui.user_id = {alias}.user_id
              AND ui.identity_type = 'telegram_hash'
            ORDER BY ui.identity_id
            LIMIT 1
        ),
        (
            SELECT ui.identity_value
            FROM user_identities ui
            WHERE ui.user_id = {alias}.user_id
            ORDER BY ui.identity_id
            LIMIT 1
        )
    )
    """


# ---------------------------------------------------------------------------
# Campaigns / Placements compatibility API for the existing Streamlit app
# placement in UI == marketing_activity in PostgreSQL
# ---------------------------------------------------------------------------

def create_campaign(
    campaign_id,
    name,
    objective=None,
    target_course=None,
    start_date=None,
    end_date=None,
    budget=None,
    notes=None,
    data_origin="observed",
):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO campaigns (
                campaign_key,
                campaign_name,
                started_at,
                ended_at,
                description,
                objective,
                target_course_text,
                budget,
                notes,
                data_origin
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                campaign_id,
                name,
                _to_dt(start_date) if start_date else None,
                _to_dt(end_date) if end_date else None,
                notes,
                objective,
                target_course,
                budget,
                notes,
                data_origin,
            ),
        )


def update_campaign(campaign_id: str, **fields):
    mapping = {
        "name": "campaign_name",
        "objective": "objective",
        "target_course": "target_course_text",
        "start_date": "started_at",
        "end_date": "ended_at",
        "budget": "budget",
        "notes": "notes",
    }

    updates = []
    values = []
    for key, value in fields.items():
        column = mapping.get(key)
        if not column:
            continue
        if key in {"start_date", "end_date"} and value:
            value = _to_dt(value)
        updates.append(f"{column} = %s")
        values.append(value)

    if not updates:
        return

    values.append(campaign_id)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE campaigns
            SET {", ".join(updates)}
            WHERE campaign_key = %s
            """,
            values,
        )


def delete_campaign(campaign_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT campaign_id FROM campaigns WHERE campaign_key = %s",
            (campaign_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        internal_id = row["campaign_id"]
        # Preserve old app semantics: deleting a campaign also removes placements.
        cur.execute(
            "DELETE FROM marketing_activities WHERE campaign_id = %s",
            (internal_id,),
        )
        cur.execute(
            "DELETE FROM campaigns WHERE campaign_id = %s",
            (internal_id,),
        )


def create_placement(
    placement_id,
    campaign_id,
    channel,
    creative_id,
    cost,
    publication_time,
    target_course,
    tracking_token,
    data_origin="observed",
):
    with get_conn() as conn, conn.cursor() as cur:
        internal_campaign_id = _resolve_campaign_id(cur, campaign_id)
        course_id = _ensure_course(cur, target_course)

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
                creative_id,
                is_deleted,
                data_origin
            )
            VALUES (
                %s, %s, 'placement', %s, %s, %s, %s, NULL,
                %s, %s, %s, FALSE, %s
            )
            """,
            (
                internal_campaign_id,
                course_id,
                channel,
                _to_dt(publication_time) if publication_time else None,
                cost,
                tracking_token,
                placement_id,
                target_course,
                creative_id,
                data_origin,
            ),
        )


def update_placement(placement_id: str, **fields):
    mapping = {
        "campaign_id": "campaign_id",
        "channel": "channel_name",
        "creative_id": "creative_id",
        "cost": "cost",
        "publication_time": "published_at",
        "target_course": "course_target_text",
        "tracking_token": "tracking_code",
    }

    with get_conn() as conn, conn.cursor() as cur:
        updates = []
        values = []

        for key, value in fields.items():
            column = mapping.get(key)
            if not column:
                continue

            if key == "campaign_id":
                value = _resolve_campaign_id(cur, value)
            elif key == "publication_time" and value:
                value = _to_dt(value)
            elif key == "target_course":
                # Keep both the raw UI label and an exact course FK when possible.
                course_id = _ensure_course(cur, value)
                updates.append("course_id = %s")
                values.append(course_id)

            updates.append(f"{column} = %s")
            values.append(value)

        if not updates:
            return

        values.append(placement_id)
        cur.execute(
            f"""
            UPDATE marketing_activities
            SET {", ".join(updates)}
            WHERE source_activity_key = %s
            """,
            values,
        )


def delete_placement(placement_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM marketing_activities
            WHERE source_activity_key = %s
            """,
            (placement_id,),
        )


def list_campaigns():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                campaign_key AS campaign_id,
                campaign_name AS name,
                objective,
                target_course_text AS target_course,
                started_at AS start_date,
                ended_at AS end_date,
                budget,
                notes,
                created_at
            FROM campaigns
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["start_date"] = _iso(item["start_date"])
        item["end_date"] = _iso(item["end_date"])
        item["created_at"] = _iso(item["created_at"])
        if item["budget"] is not None:
            item["budget"] = float(item["budget"])
        result.append(item)
    return result


def list_placements():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ma.source_activity_key AS placement_id,
                c.campaign_key AS campaign_id,
                ma.channel_name AS channel,
                ma.creative_id,
                ma.cost,
                ma.published_at AS publication_time,
                COALESCE(ma.course_target_text, crs.course_name) AS target_course,
                ma.tracking_code AS tracking_token,
                ma.created_at
            FROM marketing_activities ma
            LEFT JOIN campaigns c
              ON c.campaign_id = ma.campaign_id
            LEFT JOIN courses crs
              ON crs.course_id = ma.course_id
            WHERE ma.source_activity_key IS NOT NULL
              AND ma.tracking_code IS NOT NULL
            ORDER BY ma.created_at DESC
            """
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["cost"] = float(item["cost"] or 0)
        item["publication_time"] = _iso(item["publication_time"])
        item["created_at"] = _iso(item["created_at"])
        result.append(item)
    return result


def get_placement_by_token(token):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ma.source_activity_key AS placement_id,
                c.campaign_key AS campaign_id,
                ma.channel_name AS channel,
                ma.creative_id,
                ma.cost,
                ma.published_at AS publication_time,
                COALESCE(ma.course_target_text, crs.course_name) AS target_course,
                ma.tracking_code AS tracking_token,
                ma.created_at
            FROM marketing_activities ma
            LEFT JOIN campaigns c
              ON c.campaign_id = ma.campaign_id
            LEFT JOIN courses crs
              ON crs.course_id = ma.course_id
            WHERE ma.tracking_code = %s
            """,
            (token,),
        )
        row = cur.fetchone()

    if not row:
        return None

    item = dict(row)
    item["cost"] = float(item["cost"] or 0)
    item["publication_time"] = _iso(item["publication_time"])
    item["created_at"] = _iso(item["created_at"])
    return item


# ---------------------------------------------------------------------------
# Users / touches / leads
# ---------------------------------------------------------------------------

def ensure_user(user_key, data_origin="observed"):
    with get_conn() as conn, conn.cursor() as cur:
        return _resolve_user_id(
            cur,
            user_key,
            create=True,
            data_origin=data_origin,
        )


def add_touch(
    user_key,
    placement_id,
    source,
    confidence,
    ts=None,
    data_origin="observed",
):
    with get_conn() as conn, conn.cursor() as cur:
        user_id = _resolve_user_id(
            cur,
            user_key,
            create=True,
            data_origin=data_origin,
        )
        activity_id = _resolve_activity_id(cur, placement_id)
        tracking_method = confidence or "unknown"
        confidence_score = _CONFIDENCE_SCORE.get(
            tracking_method,
            Decimal("0.500"),
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
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING touch_id
            """,
            (
                user_id,
                activity_id,
                _to_dt(ts) if ts else datetime.now(timezone.utc),
                source,
                tracking_method,
                confidence_score,
                data_origin,
            ),
        )
        return cur.fetchone()["touch_id"]


def list_touches():
    identity_expr = _identity_sql("u")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                t.touch_id,
                {identity_expr} AS user_key,
                ma.source_activity_key AS placement_id,
                t.touched_at AS ts,
                t.touch_type AS source,
                t.tracking_method AS confidence
            FROM touches t
            JOIN users u
              ON u.user_id = t.user_id
            JOIN marketing_activities ma
              ON ma.activity_id = t.activity_id
            ORDER BY t.touched_at DESC
            """
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["ts"] = _iso(item["ts"])
        result.append(item)
    return result


def add_lead(
    user_key,
    course=None,
    status="new",
    created_at=None,
    data_origin="observed",
):
    created_dt = _to_dt(created_at) if created_at else datetime.now(timezone.utc)

    with get_conn() as conn, conn.cursor() as cur:
        user_id = _resolve_user_id(
            cur,
            user_key,
            create=True,
            data_origin=data_origin,
        )
        course_id = _ensure_course(cur, course)

        cur.execute(
            """
            SELECT touch_id
            FROM touches
            WHERE user_id = %s
              AND touched_at <= %s
            ORDER BY touched_at DESC, touch_id DESC
            LIMIT 1
            """,
            (user_id, created_dt),
        )
        row = cur.fetchone()
        source_touch_id = row["touch_id"] if row else None

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
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING lead_id
            """,
            (
                user_id,
                course_id,
                source_touch_id,
                status,
                data_origin,
                created_dt,
            ),
        )
        return cur.fetchone()["lead_id"]


def list_leads():
    identity_expr = _identity_sql("u")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                l.lead_id,
                {identity_expr} AS user_key,
                c.course_name AS course,
                l.created_at,
                l.status
            FROM leads l
            JOIN users u
              ON u.user_id = l.user_id
            LEFT JOIN courses c
              ON c.course_id = l.course_id
            ORDER BY l.created_at DESC
            """
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["created_at"] = _iso(item["created_at"])
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def add_order(
    user_key,
    course,
    amount,
    ts,
    external_id=None,
    source_file=None,
    rule=None,
    confidence=None,
    data_origin="observed",
):
    if user_key is None:
        raise ValueError(
            "add_order(user_key=None) is no longer supported. "
            "Historical sales must be loaded through ingest_sales.py so the "
            "legacy identity is preserved and bundle orders are reconstructed."
        )

    ordered_at = _to_dt(ts)

    with get_conn() as conn, conn.cursor() as cur:
        user_id = _resolve_user_id(
            cur,
            user_key,
            create=True,
            data_origin=data_origin,
        )
        course_id = _ensure_course(cur, course)

        cur.execute(
            """
            SELECT lead_id
            FROM leads
            WHERE user_id = %s
              AND created_at <= %s
            ORDER BY created_at DESC, lead_id DESC
            LIMIT 1
            """,
            (user_id, ordered_at),
        )
        row = cur.fetchone()
        lead_id = row["lead_id"] if row else None

        source_order_key = (
            f"external:{external_id}"
            if external_id
            else f"ui:{uuid.uuid4().hex}"
        )

        if external_id:
            cur.execute(
                """
                SELECT order_id
                FROM orders
                WHERE source_order_key = %s
                """,
                (source_order_key,),
            )
            existing = cur.fetchone()
            if existing:
                return existing["order_id"]

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
                external_order_id,
                source_file,
                order_confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
            """,
            (
                user_id,
                lead_id,
                ordered_at,
                Decimal(str(amount)),
                source_order_key,
                rule,
                data_origin,
                external_id,
                source_file,
                confidence,
            ),
        )
        order_id = cur.fetchone()["order_id"]

        cur.execute(
            """
            INSERT INTO order_items (
                order_id,
                course_id,
                source_amount
            )
            VALUES (%s, %s, %s)
            """,
            (
                order_id,
                course_id,
                Decimal(str(amount)),
            ),
        )
        return order_id


def ensure_legacy_user(student_id: str):
    identity_value = str(student_id).strip()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id
            FROM user_identities
            WHERE identity_type = 'legacy_student_id'
              AND identity_value = %s
            """,
            (identity_value,),
        )
        row = cur.fetchone()
        if row:
            return row["user_id"]

        cur.execute(
            """
            INSERT INTO users (data_origin)
            VALUES ('observed')
            RETURNING user_id
            """
        )
        user_id = cur.fetchone()["user_id"]

        cur.execute(
            """
            INSERT INTO user_identities (
                user_id,
                identity_type,
                identity_value,
                data_origin
            )
            VALUES (%s, 'legacy_student_id', %s, 'observed')
            """,
            (user_id, identity_value),
        )
        return user_id


def add_reconstructed_order(
    student_id: str,
    ts,
    items: list[tuple[str, Decimal | float]],
    source_file: str | None = None,
):
    ordered_at = _to_dt(ts)
    source_order_key = f"legacy:{student_id}:{ordered_at.isoformat()}"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT order_id
            FROM orders
            WHERE source_order_key = %s
            """,
            (source_order_key,),
        )
        existing = cur.fetchone()
        if existing:
            return existing["order_id"], False

        # Resolve/create legacy user in the same transaction.
        cur.execute(
            """
            SELECT user_id
            FROM user_identities
            WHERE identity_type = 'legacy_student_id'
              AND identity_value = %s
            """,
            (str(student_id).strip(),),
        )
        row = cur.fetchone()
        if row:
            user_id = row["user_id"]
        else:
            cur.execute(
                """
                INSERT INTO users (data_origin)
                VALUES ('observed')
                RETURNING user_id
                """
            )
            user_id = cur.fetchone()["user_id"]

            cur.execute(
                """
                INSERT INTO user_identities (
                    user_id,
                    identity_type,
                    identity_value,
                    data_origin
                )
                VALUES (%s, 'legacy_student_id', %s, 'observed')
                """,
                (user_id, str(student_id).strip()),
            )

        revenue = sum(Decimal(str(amount)) for _, amount in items)
        confidence = "high" if len(items) == 1 else "medium"

        cur.execute(
            """
            INSERT INTO orders (
                user_id,
                ordered_at,
                revenue,
                source_order_key,
                reconstruction_method,
                data_origin,
                source_file,
                order_confidence
            )
            VALUES (
                %s, %s, %s, %s,
                'same_student_same_timestamp',
                'reconstructed',
                %s, %s
            )
            RETURNING order_id
            """,
            (
                user_id,
                ordered_at,
                revenue,
                source_order_key,
                source_file,
                confidence,
            ),
        )
        order_id = cur.fetchone()["order_id"]

        for course_name, amount in items:
            course_id = _ensure_course(cur, course_name)
            cur.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    course_id,
                    source_amount
                )
                VALUES (%s, %s, %s)
                """,
                (
                    order_id,
                    course_id,
                    Decimal(str(amount)),
                ),
            )

        return order_id, True


def list_orders():
    identity_expr = _identity_sql("u")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                o.order_id,
                {identity_expr} AS user_key,
                o.external_order_id AS external_id,
                STRING_AGG(
                    DISTINCT c.course_name,
                    ', ' ORDER BY c.course_name
                ) AS course,
                o.revenue AS amount,
                o.ordered_at AS ts,
                o.source_file,
                o.reconstruction_method AS order_reconstruction_rule,
                o.order_confidence
            FROM orders o
            JOIN users u
              ON u.user_id = o.user_id
            LEFT JOIN order_items oi
              ON oi.order_id = o.order_id
            LEFT JOIN courses c
              ON c.course_id = oi.course_id
            GROUP BY
                o.order_id,
                u.user_id,
                o.external_order_id,
                o.revenue,
                o.ordered_at,
                o.source_file,
                o.reconstruction_method,
                o.order_confidence
            ORDER BY o.ordered_at DESC
            """
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["amount"] = float(item["amount"])
        item["ts"] = _iso(item["ts"])
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Attribution compatibility layer
# ---------------------------------------------------------------------------

def clear_attributions(model_name: str | None = None):
    with get_conn() as conn, conn.cursor() as cur:
        if model_name:
            cur.execute(
                "DELETE FROM attributions WHERE model_name = %s",
                (model_name,),
            )
        else:
            cur.execute("DELETE FROM attributions")


def recompute_last_touch(window_days: int = 30):
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM attributions WHERE model_name = 'last_touch'"
        )

        cur.execute(
            """
            WITH ranked AS (
                SELECT
                    o.order_id,
                    o.revenue,
                    t.touch_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.order_id
                        ORDER BY t.touched_at DESC, t.touch_id DESC
                    ) AS rn
                FROM orders o
                JOIN touches t
                  ON t.user_id = o.user_id
                WHERE t.touched_at <= o.ordered_at
                  AND t.touched_at >=
                      o.ordered_at - (%s * INTERVAL '1 day')
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
                %s,
                NOW()
            FROM ranked
            WHERE rn = 1
            """,
            (window_days, window_days),
        )

        cur.execute(
            """
            SELECT
                t.tracking_method,
                COUNT(*) AS n
            FROM attributions a
            JOIN touches t
              ON t.touch_id = a.touch_id
            WHERE a.model_name = 'last_touch'
            GROUP BY t.tracking_method
            """
        )
        rows = cur.fetchall()

        summary = {
            "deterministic": 0,
            "self_reported": 0,
            "modelled": 0,
            "unknown": 0,
        }
        for row in rows:
            method = row["tracking_method"] or "unknown"
            summary[method] = int(row["n"])

        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM orders o
            WHERE NOT EXISTS (
                SELECT 1
                FROM attributions a
                WHERE a.order_id = o.order_id
                  AND a.model_name = 'last_touch'
            )
            """
        )
        summary["unknown"] = int(cur.fetchone()["n"])
        return summary


def add_attribution(
    order_id,
    placement_id,
    method,
    confidence,
    revenue_credit,
    window_days,
):
    """
    Compatibility function for old code paths.
    Unknown attribution is intentionally NOT persisted because normalized
    PostgreSQL attributions require a real touch. Unknown is derived at read time.
    """
    if placement_id is None:
        return

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                t.touch_id
            FROM orders o
            JOIN touches t
              ON t.user_id = o.user_id
            JOIN marketing_activities ma
              ON ma.activity_id = t.activity_id
            WHERE o.order_id = %s
              AND ma.source_activity_key = %s
              AND t.touched_at <= o.ordered_at
            ORDER BY t.touched_at DESC, t.touch_id DESC
            LIMIT 1
            """,
            (order_id, placement_id),
        )
        row = cur.fetchone()
        if not row:
            return

        model_name = (
            method if method in {"first_touch", "last_touch", "linear"}
            else "last_touch"
        )

        cur.execute(
            """
            INSERT INTO attributions (
                order_id,
                touch_id,
                model_name,
                attribution_weight,
                attributed_revenue,
                attribution_window_days,
                calculated_at
            )
            VALUES (%s, %s, %s, 1.00000, %s, %s, NOW())
            ON CONFLICT (order_id, touch_id, model_name)
            DO UPDATE SET
                attributed_revenue = EXCLUDED.attributed_revenue,
                attribution_window_days = EXCLUDED.attribution_window_days,
                calculated_at = NOW()
            """,
            (
                order_id,
                row["touch_id"],
                model_name,
                Decimal(str(revenue_credit)),
                window_days,
            ),
        )


def list_attributions(model_name: str = "last_touch"):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.attribution_id,
                a.order_id,
                ma.source_activity_key AS placement_id,
                a.model_name AS attribution_method,
                t.tracking_method AS confidence,
                a.attributed_revenue AS revenue_credit,
                a.attribution_window_days AS window_days,
                a.calculated_at AS computed_at
            FROM attributions a
            JOIN touches t
              ON t.touch_id = a.touch_id
            JOIN marketing_activities ma
              ON ma.activity_id = t.activity_id
            WHERE a.model_name = %s
            ORDER BY a.calculated_at DESC
            """,
            (model_name,),
        )
        attributed = cur.fetchall()

        # Preserve the old UI's "unknown" bucket without polluting the normalized
        # attributions table with fake touch records.
        cur.execute(
            """
            SELECT
                o.order_id,
                o.revenue
            FROM orders o
            WHERE NOT EXISTS (
                SELECT 1
                FROM attributions a
                WHERE a.order_id = o.order_id
                  AND a.model_name = %s
            )
            ORDER BY o.ordered_at DESC
            """,
            (model_name,),
        )
        unknown = cur.fetchall()

    result = []
    for row in attributed:
        item = dict(row)
        item["revenue_credit"] = float(item["revenue_credit"])
        item["computed_at"] = _iso(item["computed_at"])
        result.append(item)

    for row in unknown:
        result.append(
            {
                "attribution_id": None,
                "order_id": row["order_id"],
                "placement_id": None,
                "attribution_method": "unknown",
                "confidence": "unknown",
                "revenue_credit": float(row["revenue"]),
                "window_days": None,
                "computed_at": None,
            }
        )

    return result


def clear_all_data():
    """Dangerous: clear business/event data but keep the PostgreSQL schema."""
    with get_conn() as conn, conn.cursor() as cur:
        for table in (
            "incrementality_estimates",
            "attributions",
            "order_items",
            "orders",
            "leads",
            "touches",
            "activity_metric_snapshots",
            "marketing_activities",
            "campaigns",
            "user_identities",
            "users",
            "courses",
        ):
            cur.execute(f"DELETE FROM {table}")
