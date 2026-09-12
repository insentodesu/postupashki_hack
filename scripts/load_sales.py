"""
Загрузка исторических продаж base.xlsx в PostgreSQL.

Бизнес-правила:
1. Исходный student_id ("Номер студента") — обезличенный legacy-идентификатор.
   Он НЕ считается глобальным user_id системы.
2. Один исторический заказ реконструируется как:
      одинаковый student_id + одинаковый timestamp.
3. orders.revenue = сумма исходных amount внутри реконструированного заказа.
4. Каждая исходная строка = один order_item.
5. order_items.source_amount сохраняет исходный amount, но не трактуется
   как достоверная самостоятельная цена курса при bundle-покупках.
6. Пользователи/курсы/исходные строки наблюдаемы; сам исторический order_id
   отсутствует, поэтому orders.data_origin = reconstructed.
7. Загрузка идемпотентна: повторный запуск не создаёт дубли заказов.
"""

import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg


REQUIRED_COLUMNS = {
    "Номер студента",
    "Сумма",
    "Курс",
    "Время",
}


def money(value) -> Decimal:
    """Безопасное преобразование денежного значения в NUMERIC(12,2)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "postupashki"),
        user=os.getenv("POSTGRES_USER", "postupashki"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def validate_input(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"В base.xlsx отсутствуют обязательные колонки: {sorted(missing)}")

    if df[list(REQUIRED_COLUMNS)].isna().any().any():
        nulls = df[list(REQUIRED_COLUMNS)].isna().sum()
        raise ValueError(f"В обязательных колонках есть NULL:\n{nulls[nulls > 0]}")

    if (df["Сумма"] < 0).any():
        raise ValueError("Найдены отрицательные значения 'Сумма'.")

    if df["Курс"].astype(str).str.strip().eq("").any():
        raise ValueError("Найдены пустые названия курсов.")


def normalize_input(df: pd.DataFrame, source_timezone: str) -> pd.DataFrame:
    out = df.copy()

    out["Номер студента"] = out["Номер студента"].astype(str).str.strip()
    out["Курс"] = out["Курс"].astype(str).str.strip()
    out["Время"] = pd.to_datetime(out["Время"], errors="raise")

    # В base.xlsx timezone не записан.
    # Рабочее допущение задаётся явно через SOURCE_TIMEZONE.
    tz = ZoneInfo(source_timezone)
    if out["Время"].dt.tz is None:
        out["Время"] = out["Время"].dt.tz_localize(tz)

    return out


def load_sales():
    sales_file = Path(os.getenv("SALES_FILE", "/app/data/base.xlsx"))
    source_timezone = os.getenv("SOURCE_TIMEZONE", "Europe/Moscow")

    if not sales_file.exists():
        raise FileNotFoundError(
            f"Файл продаж не найден: {sales_file}. "
            "Положите base.xlsx в data/base.xlsx."
        )

    print(f"[sales] Читаю: {sales_file}")
    print(
        "[sales] SOURCE_TIMEZONE="
        f"{source_timezone} (рабочее допущение для timezone-naive timestamps)"
    )

    df = pd.read_excel(sales_file)
    validate_input(df)
    df = normalize_input(df, source_timezone)

    expected_rows = len(df)
    expected_users = df["Номер студента"].nunique()
    expected_courses = df["Курс"].nunique()
    expected_orders = df.groupby(["Номер студента", "Время"], dropna=False).ngroups

    print(
        "[sales] Входные данные: "
        f"{expected_rows} строк, "
        f"{expected_users} покупателей, "
        f"{expected_courses} курсов, "
        f"{expected_orders} reconstructed orders"
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            # ------------------------------------------------------------
            # 1. COURSES
            # ------------------------------------------------------------
            course_map = {}
            for course_name in sorted(df["Курс"].unique()):
                cur.execute(
                    """
                    INSERT INTO courses (course_name)
                    VALUES (%s)
                    ON CONFLICT (course_name)
                    DO UPDATE SET course_name = EXCLUDED.course_name
                    RETURNING course_id
                    """,
                    (course_name,),
                )
                course_map[course_name] = cur.fetchone()[0]

            # ------------------------------------------------------------
            # 2. USERS + LEGACY IDENTITIES
            # ------------------------------------------------------------
            user_map = {}

            for student_id in sorted(df["Номер студента"].unique()):
                cur.execute(
                    """
                    SELECT user_id
                    FROM user_identities
                    WHERE identity_type = 'legacy_student_id'
                      AND identity_value = %s
                    """,
                    (student_id,),
                )
                row = cur.fetchone()

                if row:
                    user_id = row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO users (data_origin)
                        VALUES ('observed')
                        RETURNING user_id
                        """
                    )
                    user_id = cur.fetchone()[0]

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
                        (user_id, student_id),
                    )

                user_map[student_id] = user_id

            # ------------------------------------------------------------
            # 3. RECONSTRUCT ORDERS + ORDER ITEMS
            # ------------------------------------------------------------
            inserted_orders = 0
            skipped_orders = 0
            inserted_items = 0

            grouped = df.groupby(
                ["Номер студента", "Время"],
                sort=True,
                dropna=False,
            )

            for (student_id, ordered_at), group in grouped:
                user_id = user_map[student_id]

                source_order_key = (
                    f"legacy:{student_id}:{ordered_at.isoformat()}"
                )
                revenue = sum(money(v) for v in group["Сумма"].tolist())

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
                    skipped_orders += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO orders (
                        user_id,
                        ordered_at,
                        revenue,
                        source_order_key,
                        reconstruction_method,
                        data_origin
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        'same_student_same_timestamp',
                        'reconstructed'
                    )
                    RETURNING order_id
                    """,
                    (
                        user_id,
                        ordered_at.to_pydatetime(),
                        revenue,
                        source_order_key,
                    ),
                )
                order_id = cur.fetchone()[0]
                inserted_orders += 1

                for _, source_row in group.iterrows():
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
                            course_map[source_row["Курс"]],
                            money(source_row["Сумма"]),
                        ),
                    )
                    inserted_items += 1

            # ------------------------------------------------------------
            # 4. CONTROL COUNTS FOR THIS HISTORICAL LOAD
            # ------------------------------------------------------------
            cur.execute(
                """
                SELECT COUNT(*)
                FROM user_identities
                WHERE identity_type = 'legacy_student_id'
                """
            )
            db_users = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM orders
                WHERE reconstruction_method = 'same_student_same_timestamp'
                  AND source_order_key LIKE 'legacy:%'
                """
            )
            db_orders = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM order_items oi
                JOIN orders o ON o.order_id = oi.order_id
                WHERE o.reconstruction_method = 'same_student_same_timestamp'
                  AND o.source_order_key LIKE 'legacy:%'
                """
            )
            db_items = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM courses")
            db_courses = cur.fetchone()[0]

    print(
        "[sales] Результат запуска: "
        f"новых orders={inserted_orders}, "
        f"пропущено существующих orders={skipped_orders}, "
        f"новых order_items={inserted_items}"
    )
    print(
        "[sales] Контроль БД: "
        f"legacy users={db_users}, "
        f"courses={db_courses}, "
        f"historical orders={db_orders}, "
        f"historical order_items={db_items}"
    )

    expected = {
        "legacy users": expected_users,
        "courses": expected_courses,
        "historical orders": expected_orders,
        "historical order_items": expected_rows,
    }
    actual = {
        "legacy users": db_users,
        "courses": db_courses,
        "historical orders": db_orders,
        "historical order_items": db_items,
    }

    mismatches = {
        k: (expected[k], actual[k])
        for k in expected
        if expected[k] != actual[k]
    }

    if mismatches:
        raise RuntimeError(
            "Контрольные числа не совпали: "
            + ", ".join(
                f"{k}: ожидалось {e}, в БД {a}"
                for k, (e, a) in mismatches.items()
            )
        )

    print("[sales] OK: контрольные числа совпали.")


if __name__ == "__main__":
    load_sales()
