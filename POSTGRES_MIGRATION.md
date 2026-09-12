# PostgreSQL integration contract

## Goal

Replace the temporary SQLite implementation with PostgreSQL as the single
source of truth while preserving the team's Streamlit demo flow.

The application-level vocabulary can remain:

`campaign -> placement -> touch -> lead -> order -> ROMI`

The physical PostgreSQL model is richer:

`campaigns -> marketing_activities -> touches -> leads -> orders/order_items`

Historical data is kept separate from synthetic demo data through `data_origin`.

---

## What is kept from the team project

No functional rewrite is required for these modules unless the SQLite scan
finds direct SQL inside them:

- `app.py` UI/layout/forms/navigation
- `src/tracking.py`
- `src/romi.py`
- `src/bot.py`
- `src/payment.py`

`src/romi.py` continues to work against the compatibility dictionaries exposed
by the new `src/db.py`. The normalized SQL views remain the authoritative
analytics layer for the richer first/last/linear and incrementality demo.

---

## Files that MUST change

### `src/db.py`

Full replacement.

Responsibilities after migration:

- connect with psycopg;
- translate old UI `placement` calls to `marketing_activities`;
- translate `user_key` to `users + user_identities`;
- insert orders as `orders + order_items`;
- derive an `unknown` attribution bucket at read time rather than inserting fake
  attribution rows;
- expose the old list/create methods so most of Streamlit does not need a rewrite.

### `src/ingest_sales.py`

Full replacement.

The SQLite version creates one order per Excel row. That loses bundle/order
semantics. PostgreSQL import uses:

`student_id + timestamp = one reconstructed order`

Therefore the known case data becomes:

- 606 legacy users
- 628 orders
- 795 order_items

Historical orders are `data_origin='reconstructed'`; user identities are
observed legacy identities. No historical ad touch is invented.

### `src/attribution.py`

Replace the Python/SQLite storage logic with a thin PostgreSQL wrapper.

The default UI action persists `last_touch` with a configurable 30-day window.
Historical orders without an eligible touch remain unknown.

The richer SQL job in `sql/jobs/001_attribution_all_models.sql` can additionally
recompute first-touch, last-touch and linear models.

### `src/seed_demo.py`

Must stop using `if db.list_campaigns(): return`, because PostgreSQL can already
contain real/reconstructed campaigns.

It now checks only its own demo campaign key and marks its rows as synthetic.

### `app.py`

Do NOT rewrite the UI.

Only the direct SQLite write helper block must be changed:

- `update_campaign`
- `delete_campaign`
- `update_placement`
- `delete_placement`
- `clear_all_data`

They must call methods in `db.py` rather than execute SQLite SQL directly.

Run:

```bash
python scripts/patch_app_for_postgres.py
```

The script fails safely if the expected block cannot be found.

One wording change is recommended on the sales import page: `ingest()` now
returns **new reconstructed orders**, not raw Excel rows.

---

## PostgreSQL schema compatibility migration

`sql/init/003_app_compatibility.sql` adds UI metadata that is useful to preserve
without weakening the normalized core model:

Campaign:
- objective
- target_course_text
- budget
- notes

Marketing activity:
- creative_id

Order:
- external_order_id
- source_file
- order_confidence

`placement_id` is NOT added as a duplicate entity. The UI-facing placement ID is
stored as `marketing_activities.source_activity_key`.

---

## Important mapping

| Existing UI concept | PostgreSQL |
|---|---|
| campaign_id | campaigns.campaign_key |
| placement_id | marketing_activities.source_activity_key |
| tracking_token | marketing_activities.tracking_code |
| channel | marketing_activities.channel_name |
| target_course | course_target_text + optional courses FK |
| user_key | user_identities(identity_type='telegram_hash') |
| touch.ts | touches.touched_at |
| touch.source | touches.touch_type |
| touch.confidence | touches.tracking_method (+ numeric confidence) |
| order.amount | orders.revenue |
| order.course | order_items -> courses |
| attribution placement | attribution -> touch -> marketing_activity |

---

## SQL directory split

Only schema/view definitions belong in Docker automatic init:

`sql/init/`

Data-dependent jobs must NOT live in `/docker-entrypoint-initdb.d`:

- `sql/jobs/001_attribution_all_models.sql`
- `sql/demo/001_seed_incrementality_demo.sql`
- `sql/demo/002_demo_report.sql`

This prevents a fresh PostgreSQL initialization from failing before demo data
exists.

---

## Data policy

Do not commit:

- `.env`
- `data/base.xlsx`
- local CSV exports unless team explicitly decides otherwise
- `data/*.db`

Commit `.env.example`.

---

## Migration verification

Run the scanner:

```bash
python scripts/check_no_sqlite.py
```

It should report no SQLite coupling outside `src/db.py`.

Then:

```bash
docker compose up --build -d db
docker compose --profile tools run --rm loader python scripts/smoke_postgres.py
```

For the historical case file:

```bash
docker compose --profile tools run --rm loader python src/ingest_sales.py
```

Expected first load:

- 606 legacy users
- 628 reconstructed orders
- 795 order_items

For the app:

```bash
docker compose up --build app
```

Open `http://localhost:8501`.

---

## Minimum acceptance tests before merge

1. Ad Registry can create/edit/delete campaign.
2. Ad Registry can create/edit/delete placement.
3. Tracking token resolves to the correct placement.
4. A simulated tracked user creates user + touch + lead.
5. A test payment creates one order + one order_item.
6. Attribution marks the tracked order as last-touch.
7. A user/order without an eligible touch appears as unknown.
8. Historical Excel import produces reconstructed orders, not 795 fake orders.
9. ROMI page opens and does not double-count multiple attribution models.
10. `python scripts/check_no_sqlite.py` passes.
11. Restarting containers preserves PostgreSQL data.
12. `git status` contains no `.env`, `.db`, xlsx or csv secrets/data.

---

## Suggested commit sequence on the feature branch

1. `chore: add postgres docker infrastructure and schema`
2. `refactor: replace sqlite adapter with postgres db layer`
3. `fix: reconstruct historical sales into orders and order items`
4. `refactor: move attribution persistence to postgres`
5. `chore: adapt streamlit db write helpers`
6. `docs: document postgres migration and demo workflow`

Keep these as separate commits so reviewers can isolate infrastructure,
data-model, and UI compatibility changes.
