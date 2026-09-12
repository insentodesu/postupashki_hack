import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import db

REQUIRED_TABLES = [
    "users",
    "user_identities",
    "courses",
    "campaigns",
    "marketing_activities",
    "touches",
    "leads",
    "orders",
    "order_items",
    "attributions",
    "incrementality_estimates",
]

REQUIRED_VIEWS = [
    "vw_sales_daily",
    "vw_marketing_activity_performance",
    "vw_campaign_performance",
    "vw_activity_romi_attr",
    "vw_campaign_romi_attr",
    "vw_incrementality_romi",
]

db.init_db()

with db.get_conn() as conn, conn.cursor() as cur:
    for name in REQUIRED_TABLES:
        cur.execute("SELECT to_regclass(%s) AS obj", (f"public.{name}",))
        assert cur.fetchone()["obj"], f"Missing table: {name}"

    for name in REQUIRED_VIEWS:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.views
                WHERE table_schema = 'public'
                  AND table_name = %s
            ) AS ok
            """,
            (name,),
        )
        assert cur.fetchone()["ok"], f"Missing view: {name}"

print("OK: PostgreSQL schema/views are available.")
print("campaigns:", len(db.list_campaigns()))
print("placements:", len(db.list_placements()))
print("touches:", len(db.list_touches()))
print("leads:", len(db.list_leads()))
print("orders:", len(db.list_orders()))
