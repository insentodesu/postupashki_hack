"""
Загрузка реконструированного marketing_posts.csv в PostgreSQL.

Принципы:
- marketing_posts.csv содержит post-level агрегаты, а НЕ user-level touches.
- campaign_id='none' означает отсутствие кампании.
- course_target (СТАРТ/ПРО/...) не насильно сопоставляется конкретному курсу.
  course_id заполняется только при ТОЧНОМ совпадении с courses.course_name;
  исходное значение всегда сохраняется в course_target_text.
- linked_spike сохраняется как исходная аналитическая пометка, но не трактуется
  как причинный эффект.
- cost и tracking_code для исторических публикаций остаются NULL.
- data_origin='reconstructed'.
- collected_at для исторического агрегатного snapshot = время первого импорта,
  потому что исходный CSV не содержит реальное время снятия TGStat-метрик.
"""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg


REQUIRED_COLUMNS = {
    "campaign_id",
    "date",
    "time",
    "type",
    "course_target",
    "discount_pct",
    "views",
    "reposts",
    "clicks_fwd",
    "comments",
    "likes",
    "summary",
    "linked_spike",
    "deleted",
}


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "postupashki"),
        user=os.getenv("POSTGRES_USER", "postupashki"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def nullable_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value or None


def nullable_int(value):
    if pd.isna(value):
        return None
    return int(value)


def nullable_float(value):
    if pd.isna(value):
        return None
    return float(value)


def parse_deleted(value) -> bool:
    text = nullable_text(value)
    if text is None:
        return False
    return text.lower().startswith("да")


def make_source_activity_key(row) -> str:
    # Метрики намеренно НЕ входят в ключ:
    # их значения могут обновиться, а публикация должна остаться той же.
    identity = "|".join(
        [
            str(row["campaign_id"]).strip(),
            str(row["date"]).strip(),
            str(row["time"]).strip(),
            str(row["type"]).strip(),
            str(row["summary"]).strip(),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"marketing_posts:{digest}"


def validate_input(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"В marketing_posts.csv отсутствуют обязательные колонки: {sorted(missing)}"
        )

    for col in ["campaign_id", "date", "time", "type", "summary", "deleted"]:
        if df[col].isna().any():
            raise ValueError(f"В обязательной колонке {col!r} есть NULL.")

    for col in ["views", "reposts", "clicks_fwd", "comments", "likes"]:
        non_null = df[col].dropna()
        if (non_null < 0).any():
            raise ValueError(f"В метрике {col!r} найдены отрицательные значения.")

    discounts = df["discount_pct"].dropna()
    if ((discounts < 0) | (discounts > 100)).any():
        raise ValueError("discount_pct должен быть в диапазоне 0..100.")


def normalize_input(df: pd.DataFrame, source_timezone: str) -> pd.DataFrame:
    out = df.copy()

    out["campaign_id"] = out["campaign_id"].astype(str).str.strip()
    out["type"] = out["type"].astype(str).str.strip()
    out["summary"] = out["summary"].astype(str).str.strip()

    local_dt = pd.to_datetime(
        out["date"].astype(str).str.strip()
        + " "
        + out["time"].astype(str).str.strip(),
        errors="raise",
    )

    tz = ZoneInfo(source_timezone)
    out["published_at"] = local_dt.dt.tz_localize(tz)
    out["source_activity_key"] = out.apply(make_source_activity_key, axis=1)

    if out["source_activity_key"].duplicated().any():
        dupes = out.loc[
            out["source_activity_key"].duplicated(keep=False),
            ["date", "time", "type", "summary"],
        ]
        raise ValueError(
            "В источнике получились дубли source_activity_key:\n"
            + dupes.to_string(index=False)
        )

    return out


def ensure_migration_applied(cur):
    cur.execute(
        """
        SELECT
            EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'marketing_activities'
                  AND column_name = 'source_activity_key'
            )
        """
    )
    if not cur.fetchone()[0]:
        raise RuntimeError(
            "Миграция 002_marketing_source_fields.sql ещё не применена. "
            "Сначала выполните её через psql."
        )


def load_marketing():
    marketing_file = Path(
        os.getenv("MARKETING_FILE", "/app/data/marketing_posts.csv")
    )
    source_timezone = os.getenv("SOURCE_TIMEZONE", "Europe/Moscow")

    if not marketing_file.exists():
        raise FileNotFoundError(
            f"Файл не найден: {marketing_file}. "
            "Положите marketing_posts.csv в data/marketing_posts.csv."
        )

    print(f"[marketing] Читаю: {marketing_file}")
    print(
        "[marketing] SOURCE_TIMEZONE="
        f"{source_timezone} (рабочее допущение для timezone-naive timestamps)"
    )

    df = pd.read_csv(marketing_file)
    validate_input(df)
    df = normalize_input(df, source_timezone)

    campaign_keys = sorted(
        c for c in df["campaign_id"].unique()
        if c.lower() != "none"
    )

    print(
        "[marketing] Входные данные: "
        f"{len(df)} публикаций, "
        f"{len(campaign_keys)} campaign keys"
    )

    snapshot_loaded_at = datetime.now(timezone.utc)

    with get_connection() as conn:
        with conn.cursor() as cur:
            ensure_migration_applied(cur)

            # ------------------------------------------------------------
            # 1. CAMPAIGNS
            # ------------------------------------------------------------
            campaign_map = {}

            for campaign_key in campaign_keys:
                cur.execute(
                    """
                    INSERT INTO campaigns (
                        campaign_key,
                        campaign_name,
                        data_origin
                    )
                    VALUES (%s, %s, 'reconstructed')
                    ON CONFLICT (campaign_key)
                    DO UPDATE SET
                        campaign_name = EXCLUDED.campaign_name
                    RETURNING campaign_id
                    """,
                    (campaign_key, campaign_key),
                )
                campaign_map[campaign_key] = cur.fetchone()[0]

            # ------------------------------------------------------------
            # 2. EXACT COURSE LOOKUP ONLY
            # ------------------------------------------------------------
            cur.execute("SELECT course_name, course_id FROM courses")
            exact_course_map = {
                course_name: course_id
                for course_name, course_id in cur.fetchall()
            }

            inserted_activities = 0
            updated_activities = 0
            inserted_snapshots = 0
            updated_snapshots = 0

            # ------------------------------------------------------------
            # 3. ACTIVITIES + AGGREGATE METRIC SNAPSHOTS
            # ------------------------------------------------------------
            for _, row in df.iterrows():
                source_key = row["source_activity_key"]
                campaign_key = str(row["campaign_id"]).strip()
                campaign_id = (
                    None
                    if campaign_key.lower() == "none"
                    else campaign_map[campaign_key]
                )

                course_target = nullable_text(row["course_target"])
                course_id = (
                    exact_course_map.get(course_target)
                    if course_target is not None
                    else None
                )

                cur.execute(
                    """
                    SELECT activity_id
                    FROM marketing_activities
                    WHERE source_activity_key = %s
                    """,
                    (source_key,),
                )
                existing = cur.fetchone()

                params = (
                    campaign_id,
                    course_id,
                    str(row["type"]).strip(),
                    "Telegram",
                    row["published_at"].to_pydatetime(),
                    nullable_float(row["discount_pct"]),
                    str(row["summary"]).strip(),
                    course_target,
                    nullable_text(row["linked_spike"]),
                    parse_deleted(row["deleted"]),
                    source_key,
                )

                if existing:
                    activity_id = existing[0]
                    cur.execute(
                        """
                        UPDATE marketing_activities
                        SET
                            campaign_id = %s,
                            course_id = %s,
                            activity_type = %s,
                            channel_name = %s,
                            published_at = %s,
                            discount_pct = %s,
                            summary = %s,
                            course_target_text = %s,
                            linked_spike = %s,
                            is_deleted = %s,
                            data_origin = 'reconstructed'
                        WHERE source_activity_key = %s
                        """,
                        params,
                    )
                    updated_activities += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO marketing_activities (
                            campaign_id,
                            course_id,
                            activity_type,
                            channel_name,
                            published_at,
                            cost,
                            discount_pct,
                            tracking_code,
                            summary,
                            data_origin,
                            course_target_text,
                            linked_spike,
                            is_deleted,
                            source_activity_key
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            NULL, %s, NULL, %s, 'reconstructed',
                            %s, %s, %s, %s
                        )
                        RETURNING activity_id
                        """,
                        params[:-1] + (source_key,),
                    )
                    activity_id = cur.fetchone()[0]
                    inserted_activities += 1

                metrics = (
                    nullable_int(row["views"]),
                    nullable_int(row["reposts"]),
                    nullable_int(row["comments"]),
                    nullable_int(row["likes"]),
                    nullable_int(row["clicks_fwd"]),
                )

                # Для одного исторического CSV держим один reconstructed snapshot
                # на activity. Повторный импорт обновляет его, а не плодит строки.
                cur.execute(
                    """
                    SELECT snapshot_id
                    FROM activity_metric_snapshots
                    WHERE activity_id = %s
                      AND data_origin = 'reconstructed'
                    ORDER BY snapshot_id
                    LIMIT 1
                    """,
                    (activity_id,),
                )
                snapshot = cur.fetchone()

                if snapshot:
                    cur.execute(
                        """
                        UPDATE activity_metric_snapshots
                        SET
                            views = %s,
                            reposts = %s,
                            comments = %s,
                            likes = %s,
                            clicks_fwd = %s
                        WHERE snapshot_id = %s
                        """,
                        metrics + (snapshot[0],),
                    )
                    updated_snapshots += 1
                else:
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
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            'reconstructed'
                        )
                        """,
                        (
                            activity_id,
                            snapshot_loaded_at,
                            *metrics,
                        ),
                    )
                    inserted_snapshots += 1

            # ------------------------------------------------------------
            # 4. CONTROL COUNTS
            # ------------------------------------------------------------
            cur.execute(
                """
                SELECT COUNT(*)
                FROM marketing_activities
                WHERE source_activity_key LIKE 'marketing_posts:%'
                """
            )
            db_activities = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM activity_metric_snapshots s
                JOIN marketing_activities a
                  ON a.activity_id = s.activity_id
                WHERE a.source_activity_key LIKE 'marketing_posts:%'
                  AND s.data_origin = 'reconstructed'
                """
            )
            db_snapshots = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM campaigns
                WHERE campaign_key = ANY(%s)
                """,
                (campaign_keys,),
            )
            db_campaigns = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM marketing_activities
                WHERE source_activity_key LIKE 'marketing_posts:%'
                  AND course_id IS NOT NULL
                """
            )
            exact_course_links = cur.fetchone()[0]

    print(
        "[marketing] Результат запуска: "
        f"activities inserted={inserted_activities}, "
        f"updated={updated_activities}; "
        f"snapshots inserted={inserted_snapshots}, "
        f"updated={updated_snapshots}"
    )
    print(
        "[marketing] Контроль БД: "
        f"campaigns={db_campaigns}, "
        f"activities={db_activities}, "
        f"snapshots={db_snapshots}, "
        f"exact course links={exact_course_links}"
    )

    if db_campaigns != len(campaign_keys):
        raise RuntimeError(
            f"Ожидалось campaigns={len(campaign_keys)}, в БД {db_campaigns}"
        )
    if db_activities != len(df):
        raise RuntimeError(
            f"Ожидалось activities={len(df)}, в БД {db_activities}"
        )
    if db_snapshots != len(df):
        raise RuntimeError(
            f"Ожидалось snapshots={len(df)}, в БД {db_snapshots}"
        )

    print("[marketing] OK: контрольные числа совпали.")
    print(
        "[marketing] Важно: отсутствие exact course links допустимо — "
        "СТАРТ/ПРО являются marketing targets, а не точными course_name."
    )


if __name__ == "__main__":
    load_marketing()
