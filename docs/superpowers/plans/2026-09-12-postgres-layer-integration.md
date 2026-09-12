# PostgreSQL Layer Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the database teammate's PostgreSQL-backed Streamlit layer without replacing or breaking the deployed Vercel/Neon application.

**Architecture:** Keep `web/` as the production Vercel application and its existing Neon schema. Add the teammate's normalized PostgreSQL adapter only to the root Streamlit/Docker runtime, with explicit environment boundaries and no cross-schema imports. Harden the shared Python tracking module and dependencies before opening a merge PR.

**Tech Stack:** Python 3.12, Streamlit, psycopg 3, PostgreSQL 16, Docker Compose, Next.js/Vercel, pytest and Vitest.

---

### Task 1: Preserve the integration boundary

**Files:**
- Create: `docs/superpowers/plans/2026-09-12-postgres-layer-integration.md`
- Inspect: `web/lib/db/schema.sql`, `sql/init/001_schema.sql`, `POSTGRES_MIGRATION.md`

- [ ] **Step 1: Verify the two schemas are intentionally separate**

Run:

```bash
git diff --stat origin/main...refs/remotes/vs/feature/postgres-measurement
rg -n "CREATE TABLE|CREATE VIEW" web/lib/db/schema.sql sql/init
```

Expected: the Vercel schema uses `placements/orders/attributions`, while the Python migration uses `marketing_activities/order_items`.

- [ ] **Step 2: Keep the branch merge isolated**

Use `integration/postgres-db-review` as the only branch receiving the PostgreSQL layer. Do not change `web/lib/db/*` or Vercel environment variables in this integration.

### Task 2: Add the normalized PostgreSQL Streamlit layer

**Files:**
- Add: `sql/init/*.sql`, `sql/jobs/*.sql`, `sql/demo/*.sql`
- Add: `src/db.py`, `scripts/*.py`, `POSTGRES_MIGRATION.md`, `schema_dictionary.md`
- Modify: `app.py`, `src/attribution.py`, `src/ingest_sales.py`, `src/seed_demo.py`, `docker-compose.yml`, `Dockerfile`

- [ ] **Step 1: Merge the colleague branch without changing `web/`**

```bash
git merge --no-commit --no-ff refs/remotes/vs/feature/postgres-measurement
```

Expected: root Streamlit files and SQL migrations are added; `web/` remains unchanged.

- [ ] **Step 2: Verify the adapter contract**

```bash
python3 scripts/check_no_sqlite.py
python3 -m compileall -q app.py src scripts
```

Expected: the scanner prints `OK: no obvious SQLite coupling outside src/db.py.` and compilation exits successfully.

### Task 3: Harden shared Python configuration

**Files:**
- Modify: `src/tracking.py`, `.env.example`, `requirements.txt`

- [ ] **Step 1: Require an explicit hash secret**

Replace the module-level fallback with a function that raises `RuntimeError("USER_HASH_SECRET is required")` when the variable is missing. Keep HMAC-SHA256 and the existing 32-character key format.

- [ ] **Step 2: Declare runtime dependencies**

Keep `psycopg[binary]`, `python-telegram-bot`, `pytest`, `stripe`, `qrcode[pil]`, `streamlit`, `pandas`, and `openpyxl` in `requirements.txt`.

- [ ] **Step 3: Validate configuration examples**

Set `USER_HASH_SECRET=` in `.env.example` and document that operators must provide a random value before starting the bot or Streamlit app.

### Task 4: Verify both runtimes independently

**Files:**
- Test: `web/tests/*.test.ts`
- Test: `scripts/check_no_sqlite.py`, `scripts/smoke_postgres.py`

- [ ] **Step 1: Validate Python static checks**

```bash
python3 scripts/check_no_sqlite.py
python3 -m compileall -q app.py src scripts
cp .env.example .env
docker compose config --quiet
rm -f .env
```

Expected: all commands succeed; `.env` is not committed.

- [ ] **Step 2: Validate the production web runtime**

```bash
cd web
npm test
npm run lint
npm run typecheck
npm run build
```

Expected: all Vitest tests pass and the Next.js production build succeeds.

### Task 5: Publish for team review, not direct production replacement

**Files:**
- Commit: all files above

- [ ] **Step 1: Commit the integration branch**

```bash
git add .
git commit -m "feat: integrate postgres streamlit measurement layer"
```

- [ ] **Step 2: Push and open a pull request**

```bash
git push -u origin integration/postgres-db-review
gh pr create --base main --head integration/postgres-db-review
```

The PR must state that `web/` remains on the existing Neon schema and that the root Streamlit runtime uses the new PostgreSQL schema.

- [ ] **Step 3: Merge only after the PR checks pass**

Required evidence: Python static checks, web tests/build, Docker Compose config, and a real PostgreSQL smoke run with 606 users, 628 reconstructed orders, and 795 order items.
