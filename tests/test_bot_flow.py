import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    psycopg_stub = types.ModuleType("psycopg")
    psycopg_stub.connect = lambda *args, **kwargs: None
    psycopg_rows_stub = types.ModuleType("psycopg.rows")
    psycopg_rows_stub.dict_row = object()
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = psycopg_rows_stub

import bot


class Message:
    def __init__(self, text=None):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


def test_start_without_placement_records_unknown_touch(monkeypatch):
    touches = []
    monkeypatch.setattr(bot.tracking, "user_key_from_telegram_id", lambda _: "hashed")
    monkeypatch.setattr(bot.db, "ensure_user", lambda _: None)
    monkeypatch.setattr(bot.db, "get_placement_by_token", lambda _: None)
    monkeypatch.setattr(
        bot.db,
        "add_touch",
        lambda *args, **kwargs: touches.append((args, kwargs)),
    )

    message = Message("/start")
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=message,
    )
    ctx = SimpleNamespace(args=[])

    asyncio.run(bot.start(update, ctx))

    assert touches == [(('hashed', None), {"source": "organic", "confidence": "unknown"})]
    assert "источник неизвестен" in message.replies[0]


def test_manager_cta_creates_lead_without_claiming_delivery(monkeypatch):
    monkeypatch.setattr(bot.tracking, "user_key_from_telegram_id", lambda _: "hashed")
    monkeypatch.setattr(
        bot.db,
        "latest_touch",
        lambda _: {"target_course": "Математика"},
    )
    leads = []
    monkeypatch.setattr(
        bot.db,
        "add_lead",
        lambda user_key, course=None: leads.append((user_key, course)) or 7,
    )

    class Query:
        data = "manager"

        async def answer(self):
            return None

        async def edit_message_text(self, text):
            self.text = text

    query = Query()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42),
    )

    asyncio.run(bot.on_callback(update, SimpleNamespace()))

    assert leads == [("hashed", "Математика")]
    assert "Интерес сохранён" in query.text
    assert "передал" not in query.text.lower()
