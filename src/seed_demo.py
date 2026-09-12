"""Small UI demo compatible with the PostgreSQL data model."""

from datetime import datetime, timezone, timedelta

import db
import tracking


DEMO_CAMPAIGN_ID = "shad_sep26"


def seed():
    db.init_db()

    if any(c["campaign_id"] == DEMO_CAMPAIGN_ID for c in db.list_campaigns()):
        print("Demo already seeded.")
        return

    db.create_campaign(
        DEMO_CAMPAIGN_ID,
        "Сентябрьский запуск",
        objective="Leads",
        target_course="Python-разработчик",
        budget=300000,
        start_date="2026-09-01",
        end_date="2026-09-30",
        data_origin="synthetic",
    )

    db.create_placement(
        "tg_channel_a_001",
        DEMO_CAMPAIGN_ID,
        "@channel_a",
        "creative_01",
        50000,
        "2026-09-05T10:00:00+03:00",
        "Python-разработчик",
        "p_a001",
        data_origin="synthetic",
    )
    db.create_placement(
        "tg_channel_b_001",
        DEMO_CAMPAIGN_ID,
        "@channel_b",
        "creative_02",
        30000,
        "2026-09-06T10:00:00+03:00",
        "Python-разработчик",
        "p_b001",
        data_origin="synthetic",
    )

    now = datetime.now(timezone.utc)

    u1 = tracking.user_key_from_telegram_id("1001")
    db.ensure_user(u1, data_origin="synthetic")
    db.add_touch(
        u1,
        "tg_channel_a_001",
        "bot_deeplink",
        "deterministic",
        ts=(now - timedelta(days=5)).isoformat(),
        data_origin="synthetic",
    )
    db.add_lead(
        u1,
        "Python-разработчик",
        created_at=(now - timedelta(days=5)).isoformat(),
        data_origin="synthetic",
    )
    db.add_order(
        u1,
        "Python-разработчик",
        19990,
        ts=(now - timedelta(days=3)).isoformat(),
        external_id="demo_1",
        data_origin="synthetic",
    )

    u2 = tracking.user_key_from_telegram_id("1002")
    db.ensure_user(u2, data_origin="synthetic")
    db.add_touch(
        u2,
        "tg_channel_a_001",
        "bot_deeplink",
        "deterministic",
        ts=(now - timedelta(days=4)).isoformat(),
        data_origin="synthetic",
    )
    db.add_order(
        u2,
        "Python-разработчик",
        19990,
        ts=(now - timedelta(days=1)).isoformat(),
        external_id="demo_2",
        data_origin="synthetic",
    )

    u3 = tracking.user_key_from_telegram_id("1003")
    db.ensure_user(u3, data_origin="synthetic")
    db.add_touch(
        u3,
        "tg_channel_b_001",
        "promo_code",
        "self_reported",
        ts=(now - timedelta(days=6)).isoformat(),
        data_origin="synthetic",
    )
    db.add_order(
        u3,
        "Python-разработчик",
        19990,
        ts=now.isoformat(),
        external_id="demo_3",
        data_origin="synthetic",
    )

    # no touch -> remains unknown after attribution
    u4 = tracking.user_key_from_telegram_id("1004")
    db.ensure_user(u4, data_origin="synthetic")
    db.add_order(
        u4,
        "Python-разработчик",
        19990,
        ts=now.isoformat(),
        external_id="demo_4",
        data_origin="synthetic",
    )

    print("PostgreSQL demo seeded.")


if __name__ == "__main__":
    seed()
