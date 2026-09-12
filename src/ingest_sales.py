"""
base.xlsx -> PostgreSQL transaction layer.

Historical rule:
    same student_id + same timestamp = one reconstructed order.

The original source rows become order_items.
Historical sales do NOT receive invented marketing attribution.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import db


COLUMN_MAP = {
    # Russian case file
    "номер студента": "student_id",
    "сумма": "amount",
    "курс": "course",
    "время": "ts",

    # English aliases
    "student_id": "student_id",
    "studentid": "student_id",
    "id": "student_id",
    "course": "course",
    "course_name": "course",
    "product": "course",
    "amount": "amount",
    "price": "amount",
    "revenue": "amount",
    "date": "ts",
    "timestamp": "ts",
    "paid_at": "ts",
    "purchase_date": "ts",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_names = {
        c: str(c).strip().lower()
        for c in df.columns
    }
    df = df.rename(columns=normalized_names)

    mapping = {
        c: COLUMN_MAP[c]
        for c in df.columns
        if c in COLUMN_MAP
    }

    required = {"student_id", "amount", "course", "ts"}
    found = set(mapping.values())
    missing = required - found
    if missing:
        raise ValueError(
            f"Не найдены обязательные поля {sorted(missing)}. "
            f"Колонки файла: {list(df.columns)}"
        )

    out = df[list(mapping)].rename(columns=mapping)
    return out[["student_id", "amount", "course", "ts"]]


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["student_id"] = out["student_id"].astype(str).str.strip()
    out["course"] = out["course"].astype(str).str.strip()
    out["amount"] = pd.to_numeric(out["amount"], errors="raise")
    out["ts"] = pd.to_datetime(out["ts"], errors="raise")

    if out[["student_id", "course", "amount", "ts"]].isna().any().any():
        raise ValueError("В обязательных колонках base.xlsx есть NULL.")

    if (out["amount"] < 0).any():
        raise ValueError("В base.xlsx найдены отрицательные суммы.")

    tz = ZoneInfo(
        __import__("os").getenv("SOURCE_TIMEZONE", "Europe/Moscow")
    )
    if out["ts"].dt.tz is None:
        out["ts"] = out["ts"].dt.tz_localize(tz)

    return out


def ingest(path: Path):
    """
    Returns number of NEW reconstructed orders inserted.
    The function is idempotent via orders.source_order_key.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    raw = pd.read_excel(path)
    df = _prepare(_normalize_columns(raw))

    inserted_orders = 0
    grouped = df.groupby(
        ["student_id", "ts"],
        sort=True,
        dropna=False,
    )

    for (student_id, ts), group in grouped:
        items = [
            (str(row["course"]), row["amount"])
            for _, row in group.iterrows()
        ]
        _, inserted = db.add_reconstructed_order(
            student_id=student_id,
            ts=ts.to_pydatetime(),
            items=items,
            source_file=path.name,
        )
        inserted_orders += int(inserted)

    return inserted_orders


if __name__ == "__main__":
    db.init_db()
    inserted = ingest(Path("data/base.xlsx"))
    print(f"Inserted reconstructed orders: {inserted}")
