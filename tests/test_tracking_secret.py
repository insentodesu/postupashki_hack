import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def test_user_hash_requires_explicit_secret(monkeypatch):
    monkeypatch.delenv("USER_HASH_SECRET", raising=False)
    import tracking

    importlib.reload(tracking)
    with pytest.raises(RuntimeError, match="USER_HASH_SECRET is required"):
        tracking.user_key_from_telegram_id("123")
