"""
Тестовая оплата через Stripe (test mode).
Реальные деньги не списываются. Используем preset test payment methods.

Ключи берутся в порядке приоритета:
  1) .streamlit/secrets.toml → [stripe] secret_key/public_key
  2) переменные окружения STRIPE_SECRET_KEY / STRIPE_PUBLIC_KEY

Тестовые карты:
  4242 4242 4242 4242 — success
  4000 0000 0000 0002 — generic decline
  4000 0000 0000 9995 — insufficient funds
  4000 0027 6000 3184 — 3DS required
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import stripe

# ---------- Config ----------

SECRET_KEY: str | None = None
PUBLIC_KEY: str | None = None


def _get_key(name: str) -> str | None:
    """st.secrets → env. Возвращает None, если ничего не задано."""
    # 1) Streamlit secrets
    try:
        import streamlit as st  # noqa: WPS433
        try:
            section = st.secrets["stripe"]        # type: ignore[index]
            value = section.get(name)
            if value:
                return str(value)
        except (KeyError, FileNotFoundError):
            pass
    except Exception:
        pass
    # 2) env vars
    return os.environ.get(name.upper())


def _reload_keys() -> None:
    global SECRET_KEY, PUBLIC_KEY
    SECRET_KEY = _get_key("secret_key")
    PUBLIC_KEY = _get_key("public_key")
    if SECRET_KEY:
        stripe.api_key = SECRET_KEY


def is_configured() -> bool:
    _reload_keys()
    return bool(SECRET_KEY)


def public_key() -> str | None:
    _reload_keys()
    return PUBLIC_KEY


# ---------- Test scenarios ----------

TEST_SCENARIOS: dict[str, dict[str, str]] = {
    "success": {
        "label": "✅ Успешная оплата",
        "pm": "pm_card_visa",
        "expected": "succeeded",
        "card": "4242 4242 4242 4242",
    },
    "decline": {
        "label": "❌ Карта отклонена",
        "pm": "pm_card_visa_chargeDeclined",
        "expected": "requires_payment_method",
        "card": "4000 0000 0000 0002",
    },
    "insufficient_funds": {
        "label": "💸 Недостаточно средств",
        "pm": "pm_card_visa_chargeDeclinedInsufficientFunds",
        "expected": "requires_payment_method",
        "card": "4000 0000 0000 9995",
    },
    "three_ds": {
        "label": "🔐 Требует 3DS (не завершится в CLI)",
        "pm": "pm_card_threeDSecure2Required",
        "expected": "requires_action",
        "card": "4000 0027 6000 3184",
    },
}


# ---------- Result ----------

@dataclass
class PaymentResult:
    ok: bool
    status: str
    intent_id: str | None
    amount: float
    currency: str
    error: str | None = None


# ---------- API ----------

def create_test_payment(
    amount: float,
    currency: str = "rub",
    description: str = "Test payment",
    metadata: dict | None = None,
    scenario: str = "success",
) -> PaymentResult:
    """
    Создаёт и подтверждает PaymentIntent в test mode.
    `amount` — в основных единицах валюты (₽), внутри конвертируется в копейки.
    """
    _reload_keys()

    if not is_configured():
        return PaymentResult(
            ok=False, status="not_configured", intent_id=None,
            amount=amount, currency=currency,
            error="Stripe не настроен (нет STRIPE_SECRET_KEY / st.secrets).",
        )

    sc = TEST_SCENARIOS.get(scenario)
    if not sc:
        return PaymentResult(
            ok=False, status="bad_scenario", intent_id=None,
            amount=amount, currency=currency,
            error=f"Unknown scenario: {scenario}",
        )

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(amount * 100)),
            currency=currency,
            description=description,
            metadata=metadata or {},
            payment_method=sc["pm"],
            confirm=True,
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never",
            },
        )
    except stripe.error.CardError as e:            # type: ignore[attr-defined]
        return PaymentResult(
            ok=False, status="card_error", intent_id=None,
            amount=amount, currency=currency,
            error=str(getattr(e, "user_message", None) or e),
        )
    except stripe.error.StripeError as e:          # type: ignore[attr-defined]
        return PaymentResult(
            ok=False, status="stripe_error", intent_id=None,
            amount=amount, currency=currency,
            error=str(e),
        )
    except Exception as e:                          # noqa: BLE001
        return PaymentResult(
            ok=False, status="unexpected_error", intent_id=None,
            amount=amount, currency=currency,
            error=str(e),
        )

    ok = intent.status == "succeeded"
    return PaymentResult(
        ok=ok,
        status=intent.status,
        intent_id=intent.id,
        amount=intent.amount / 100,
        currency=intent.currency,
        error=None if ok else f"Stripe status: {intent.status}",
    )