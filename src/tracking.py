import hashlib
import hmac
import os
import secrets

def _hash_secret() -> bytes:
    secret = os.environ.get("USER_HASH_SECRET", "").strip()
    if not secret:
        raise RuntimeError("USER_HASH_SECRET is required")
    return secret.encode()


def user_key_from_telegram_id(telegram_id) -> str:
    """HMAC-SHA256 от telegram_id. Реальный PII в аналитике не хранится."""
    msg = str(telegram_id).encode()
    return hmac.new(_hash_secret(), msg, hashlib.sha256).hexdigest()[:32]


def new_tracking_token(prefix: str = "p") -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def build_deeplink(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"
