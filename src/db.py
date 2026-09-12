import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "measurement.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    objective TEXT,
    target_course TEXT,
    start_date TEXT,
    end_date TEXT,
    budget REAL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS placements (
    placement_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    creative_id TEXT,
    cost REAL NOT NULL DEFAULT 0,
    publication_time TEXT,
    target_course TEXT,
    tracking_token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS touches (
    touch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    placement_id TEXT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence TEXT NOT NULL,
    FOREIGN KEY (user_key) REFERENCES users(user_key),
    FOREIGN KEY (placement_id) REFERENCES placements(placement_id)
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT NOT NULL,
    course TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    FOREIGN KEY (user_key) REFERENCES users(user_key)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key TEXT,
    external_id TEXT,
    course TEXT,
    amount REAL NOT NULL,
    ts TEXT NOT NULL,
    source_file TEXT,
    order_reconstruction_rule TEXT,
    order_confidence TEXT
);

CREATE TABLE IF NOT EXISTS attributions (
    attribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    placement_id TEXT,
    attribution_method TEXT NOT NULL,
    confidence TEXT NOT NULL,
    revenue_credit REAL NOT NULL,
    window_days INTEGER NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE INDEX IF NOT EXISTS idx_touches_user ON touches(user_key);
CREATE INDEX IF NOT EXISTS idx_touches_placement ON touches(placement_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_key);
CREATE INDEX IF NOT EXISTS idx_attributions_order ON attributions(order_id);
"""


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- Campaigns / Placements ---
def create_campaign(campaign_id, name, objective=None, target_course=None,
                    start_date=None, end_date=None, budget=None, notes=None):
    with get_conn() as c:
        c.execute(
            """INSERT INTO campaigns
               (campaign_id, name, objective, target_course, start_date, end_date,
                budget, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (campaign_id, name, objective, target_course, start_date, end_date,
             budget, notes, now_iso()),
        )


def create_placement(placement_id, campaign_id, channel, creative_id, cost,
                     publication_time, target_course, tracking_token):
    with get_conn() as c:
        c.execute(
            """INSERT INTO placements
               (placement_id, campaign_id, channel, creative_id, cost,
                publication_time, target_course, tracking_token, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (placement_id, campaign_id, channel, creative_id, cost,
             publication_time, target_course, tracking_token, now_iso()),
        )


def list_campaigns():
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC")]


def list_placements():
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM placements ORDER BY created_at DESC")]


def get_placement_by_token(token):
    with get_conn() as c:
        r = c.execute("SELECT * FROM placements WHERE tracking_token = ?",
                      (token,)).fetchone()
        return dict(r) if r else None


# --- Users ---
def ensure_user(user_key):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO users (user_key, created_at) VALUES (?, ?)",
                  (user_key, now_iso()))


# --- Touches ---
def add_touch(user_key, placement_id, source, confidence, ts=None):
    with get_conn() as c:
        c.execute(
            """INSERT INTO touches (user_key, placement_id, ts, source, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (user_key, placement_id, ts or now_iso(), source, confidence),
        )


def list_touches():
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM touches ORDER BY ts DESC")]


# --- Leads ---
def add_lead(user_key, course=None, status="new", created_at=None):
    with get_conn() as c:
        cur = c.execute(
            """INSERT INTO leads (user_key, course, created_at, status)
               VALUES (?, ?, ?, ?)""",
            (user_key, course, created_at or now_iso(), status),
        )
        return cur.lastrowid


def list_leads():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY created_at DESC")]


# --- Orders ---
def add_order(user_key, course, amount, ts, external_id=None,
              source_file=None, rule=None, confidence=None):
    with get_conn() as c:
        cur = c.execute(
            """INSERT INTO orders
               (user_key, external_id, course, amount, ts, source_file,
                order_reconstruction_rule, order_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_key, external_id, course, amount, ts, source_file, rule, confidence),
        )
        return cur.lastrowid


def list_orders():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY ts DESC")]


# --- Attributions ---
def clear_attributions():
    with get_conn() as c:
        c.execute("DELETE FROM attributions")


def add_attribution(order_id, placement_id, method, confidence,
                    revenue_credit, window_days):
    with get_conn() as c:
        c.execute(
            """INSERT INTO attributions
               (order_id, placement_id, attribution_method, confidence,
                revenue_credit, window_days, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, placement_id, method, confidence, revenue_credit,
             window_days, now_iso()),
        )


def list_attributions():
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM attributions ORDER BY computed_at DESC")]