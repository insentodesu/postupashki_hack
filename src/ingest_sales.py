"""
Читает base.xlsx → transaction layer.
Атрибуцию историческим продажам НЕ придумываем: user_key = NULL,
правило реконструкции заказа помечается явно.
"""
from pathlib import Path
import pandas as pd
import db

# Скорректируйте под реальные колонки base.xlsx
COLUMN_MAP = {
    "student_id": "student_id", "studentid": "student_id", "id": "student_id",
    "course": "course", "course_name": "course", "product": "course",
    "amount": "amount", "price": "amount", "revenue": "amount",
    "date": "ts", "timestamp": "ts", "paid_at": "ts", "purchase_date": "ts",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    keep = {c: COLUMN_MAP[c] for c in df.columns if c in COLUMN_MAP}
    if not keep:
        raise ValueError(f"Не найдены ожидаемые колонки. Есть: {list(df.columns)}")
    return df[list(keep)].rename(columns=keep)


def reconstruct_orders(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    df = df.dropna(subset=["ts", "amount"])

    grp = ["student_id", "ts"]
    df["group_size"] = df.groupby(grp)["amount"].transform("size")
    df["order_reconstruction_rule"] = df["group_size"].apply(
        lambda n: "single_line" if n == 1 else "same_user_same_ts_bundle"
    )
    df["order_confidence"] = df["group_size"].apply(
        lambda n: "high" if n == 1 else "medium"
    )
    return df


def ingest(path: Path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    raw = pd.read_excel(path)
    df = reconstruct_orders(_normalize_columns(raw))

    n = 0
    for _, row in df.iterrows():
        db.add_order(
            user_key=None,  # исторические данные без tracking
            course=str(row.get("course") or "").strip() or None,
            amount=float(row["amount"]),
            ts=row["ts"],
            external_id=str(row.get("student_id") or "") or None,
            source_file=path.name,
            rule=row["order_reconstruction_rule"],
            confidence=row["order_confidence"],
        )
        n += 1
    return n


if __name__ == "__main__":
    db.init_db()
    print(f"Inserted {ingest('data/base.xlsx')} rows")