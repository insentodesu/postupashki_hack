"""Заполняет систему сценарием: 2 размещения, 4 пользователя,
deterministic / self_reported / unknown пути."""
from datetime import datetime, timezone, timedelta
import db
import tracking


def seed():
    db.init_db()
    if db.list_campaigns():
        print("Already seeded.")
        return

    db.create_campaign(
        "shad_sep26", "Сентябрьский запуск", objective="Leads",
        target_course="Python-разработчик", budget=300000,
        start_date="2026-09-01", end_date="2026-09-30",
    )

    db.create_placement(
        "tg_channel_a_001", "shad_sep26", "@channel_a", "creative_01",
        50000, "2026-09-05T10:00:00", "Python-разработчик", "p_a001",
    )
    db.create_placement(
        "tg_channel_b_001", "shad_sep26", "@channel_b", "creative_02",
        30000, "2026-09-06T10:00:00", "Python-разработчик", "p_b001",
    )

    now = datetime.now(timezone.utc)

    # user 1: deterministic, из channel_a
    u1 = tracking.user_key_from_telegram_id("1001")
    db.ensure_user(u1)
    db.add_touch(u1, "tg_channel_a_001", "bot_deeplink", "deterministic",
                 ts=(now - timedelta(days=5)).isoformat())
    db.add_lead(u1, "Python-разработчик",
                created_at=(now - timedelta(days=5)).isoformat())
    db.add_order(u1, "Python-разработчик", 19990,
                 ts=(now - timedelta(days=3)).isoformat(), external_id="demo_1")

    # user 2: deterministic, из channel_a
    u2 = tracking.user_key_from_telegram_id("1002")
    db.ensure_user(u2)
    db.add_touch(u2, "tg_channel_a_001", "bot_deeplink", "deterministic",
                 ts=(now - timedelta(days=4)).isoformat())
    db.add_order(u2, "Python-разработчик", 19990,
                 ts=(now - timedelta(days=1)).isoformat(), external_id="demo_2")

    # user 3: promo-code (self_reported), channel_b
    u3 = tracking.user_key_from_telegram_id("1003")
    db.ensure_user(u3)
    db.add_touch(u3, "tg_channel_b_001", "promo_code", "self_reported",
                 ts=(now - timedelta(days=6)).isoformat())
    db.add_order(u3, "Python-разработчик", 19990,
                 ts=now.isoformat(), external_id="demo_3")

    # user 4: без tracking → unknown
    u4 = tracking.user_key_from_telegram_id("1004")
    db.ensure_user(u4)
    db.add_order(u4, "Python-разработчик", 19990,
                 ts=now.isoformat(), external_id="demo_4")

    print("Demo seeded.")


if __name__ == "__main__":
    seed()