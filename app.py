"""
Поступашки · Marketing Measurement — Streamlit UI.

Ответственность:
  • Streamlit-каркас (навигация, layout)
  • Ad Registry: создание / редактирование / удаление campaign и placement
  • Tracking-ссылки + QR
  • Симуляция событий (touch / lead / order)
  • Форма тестовой оплаты Stripe (test mode)
  • Attribution / ROMI (просмотр) + экспорт ROMI в Excel
  • Опасная зона: очистка БД
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import sys
import tempfile

import pandas as pd
import streamlit as st

# ---------- Path so src/* imports work ----------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import db                # noqa: E402
import tracking          # noqa: E402
import attribution       # noqa: E402
import romi              # noqa: E402
import seed_demo         # noqa: E402
import ingest_sales      # noqa: E402
import payment           # noqa: E402   ← наш новый файл

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False


# ---------- Page config ----------
st.set_page_config(
    page_title="Поступашки · Measurement",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

PAGES = [
    "Обзор",
    "Ad Registry",
    "Симуляция событий",
    "Импорт продаж",
    "Attribution",
    "ROMI",
]


# ============================================================
# Cached reads (15s TTL) — сбрасываются после каждой записи
# ============================================================

@st.cache_data(ttl=15, show_spinner=False)
def get_campaigns(): return db.list_campaigns()

@st.cache_data(ttl=15, show_spinner=False)
def get_placements(): return db.list_placements()

@st.cache_data(ttl=15, show_spinner=False)
def get_touches(): return db.list_touches()

@st.cache_data(ttl=15, show_spinner=False)
def get_leads(): return db.list_leads()

@st.cache_data(ttl=15, show_spinner=False)
def get_orders(): return db.list_orders()

@st.cache_data(ttl=15, show_spinner=False)
def get_attributions(): return db.list_attributions()


def bust_cache() -> None:
    for f in (get_campaigns, get_placements, get_touches,
              get_leads, get_orders, get_attributions):
        f.clear()


# ============================================================
# UI-level write helpers -> PostgreSQL adapter
# ============================================================

def update_campaign(campaign_id: str, **fields) -> None:
    db.update_campaign(campaign_id, **fields)


def delete_campaign(campaign_id: str) -> None:
    db.delete_campaign(campaign_id)


def update_placement(placement_id: str, **fields) -> None:
    db.update_placement(placement_id, **fields)


def delete_placement(placement_id: str) -> None:
    db.delete_placement(placement_id)


def clear_all_data() -> None:
    db.clear_all_data()


# ============================================================
# Page: Обзор
# ============================================================

def page_overview() -> None:
    st.title("📊 Measurement platform")
    st.caption("campaign → placement → touch → lead → order → revenue → ROMI")

    campaigns = get_campaigns()
    placements = get_placements()
    touches = get_touches()
    leads = get_leads()
    orders = get_orders()
    attrs = get_attributions()

    total_rev = sum(o["amount"] for o in orders)
    known_rev = sum(a["revenue_credit"] for a in attrs if a["placement_id"])
    unknown_rev = sum(a["revenue_credit"] for a in attrs if not a["placement_id"])
    total_spend = sum(float(p["cost"] or 0) for p in placements)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Кампании", len(campaigns))
    c2.metric("Размещения", len(placements))
    c3.metric("Touches", len(touches))
    c4.metric("Заказы", len(orders))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spend", f"{total_spend:,.0f} ₽")
    c2.metric("Revenue (всего)", f"{total_rev:,.0f} ₽")
    c3.metric("Attributed", f"{known_rev:,.0f} ₽")
    delta = (f"{unknown_rev / total_rev * 100:.0f}% от revenue"
             if total_rev else None)
    c4.metric("Unknown", f"{unknown_rev:,.0f} ₽", delta=delta, delta_color="off")

    st.info("Заказы без tracking **не приписываем рекламе** — они остаются `unknown`.")

    st.subheader("Воронка")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Touches", len(touches))
    f2.metric("Leads", len(leads))
    f3.metric("Orders", len(orders))
    conv = (len(orders) / len(touches) * 100) if touches else 0.0
    f4.metric("Touch → Order", f"{conv:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Демо")
        st.caption("Заполнить систему тестовым сценарием")
        if st.button("🌱 Загрузить демо-данные", use_container_width=True):
            seed_demo.seed()
            bust_cache()
            st.success("Демо загружено")
            st.rerun()

    with col2:
        st.subheader("Опасная зона")
        st.caption("Удалить все данные: кампании, размещения, заказы, атрибуции")
        confirm = st.checkbox("Подтверждаю удаление всех данных")
        if st.button("🗑 Очистить БД", disabled=not confirm,
                     use_container_width=True):
            clear_all_data()
            bust_cache()
            st.warning("База очищена")
            st.rerun()


# ============================================================
# Page: Ad Registry
# ============================================================

def _campaign_create_form() -> None:
    with st.form("campaign_create", clear_on_submit=False):
        st.markdown("**Новая кампания**")
        c1, c2 = st.columns(2)
        with c1:
            cid = st.text_input(
                "campaign_id", value=f"camp_{datetime.now():%Y%m%d_%H%M}")
            name = st.text_input("Название")
            objective = st.selectbox(
                "Цель", ["Awareness", "Traffic", "Leads", "Sales"])
            target_course = st.text_input("Целевой курс")
        with c2:
            budget = st.number_input("Бюджет, ₽", min_value=0.0,
                                     value=100_000.0, step=1000.0)
            start_date = st.date_input("Дата начала", value=date.today())
            end_date = st.date_input("Дата окончания", value=date.today())
            notes = st.text_area("Заметки", height=80)

        submitted = st.form_submit_button(
            "Создать кампанию", use_container_width=True)

    if not submitted:
        return

    errors: list[str] = []
    if not cid.strip():
        errors.append("campaign_id обязателен")
    if not name.strip():
        errors.append("Название обязательно")
    if end_date < start_date:
        errors.append("Дата окончания раньше даты начала")
    if any(c["campaign_id"] == cid.strip() for c in get_campaigns()):
        errors.append(f"campaign_id `{cid}` уже существует")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        db.create_campaign(
            cid.strip(), name.strip(), objective,
            target_course.strip() or None,
            str(start_date), str(end_date), budget,
            notes.strip() or None,
        )
        bust_cache()
        st.success(f"Кампания `{cid}` создана")
        st.rerun()
    except Exception as e:  # noqa: BLE001
        st.error(f"Ошибка: {e}")


def _placement_create_form() -> None:
    campaigns = get_campaigns()
    if not campaigns:
        st.warning("Сначала создайте кампанию.")
        return

    with st.form("placement_create", clear_on_submit=False):
        st.markdown("**Новое размещение**")
        c1, c2 = st.columns(2)
        with c1:
            pid = st.text_input(
                "placement_id", value=f"pl_{datetime.now():%Y%m%d_%H%M%S}")
            campaign_id = st.selectbox(
                "Кампания", [c["campaign_id"] for c in campaigns])
            channel = st.text_input("Канал", value="@channel_x")
            creative_id = st.text_input("Креатив", value="creative_01")
        with c2:
            cost = st.number_input("Стоимость, ₽", min_value=0.0,
                                   value=10_000.0, step=1000.0)
            publication_time = st.text_input(
                "Время публикации (ISO)",
                value=datetime.now().isoformat(timespec="seconds"))
            target_course = st.text_input("Курс")
            token = st.text_input(
                "Tracking token", value=tracking.new_tracking_token())

        submitted = st.form_submit_button(
            "Создать размещение", use_container_width=True)

    if not submitted:
        return

    existing = get_placements()
    errors: list[str] = []
    if not pid.strip():
        errors.append("placement_id обязателен")
    if not channel.strip():
        errors.append("Канал обязателен")
    if any(p["placement_id"] == pid.strip() for p in existing):
        errors.append(f"placement_id `{pid}` уже существует")
    if any(p["tracking_token"] == token.strip() for p in existing):
        errors.append(f"tracking_token `{token}` уже используется")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        db.create_placement(
            pid.strip(), campaign_id, channel.strip(),
            creative_id.strip() or None, cost,
            publication_time.strip() or None,
            target_course.strip() or None, token.strip(),
        )
        bust_cache()
        st.success(f"Размещение `{pid}` создано")
        st.rerun()
    except Exception as e:  # noqa: BLE001
        st.error(f"Ошибка: {e}")


def _edit_section() -> None:
    campaigns = get_campaigns()
    placements = get_placements()

    # ----- Кампании -----
    st.markdown("### Кампании")
    if not campaigns:
        st.info("Нет кампаний")
    else:
        cid = st.selectbox(
            "Выбрать кампанию",
            [c["campaign_id"] for c in campaigns],
            key="edit_camp_select",
        )
        camp = next(c for c in campaigns if c["campaign_id"] == cid)

        objective_list = ["Awareness", "Traffic", "Leads", "Sales"]
        obj_index = (objective_list.index(camp["objective"])
                     if camp.get("objective") in objective_list else 0)

        with st.form("edit_camp"):
            name = st.text_input("Название", value=camp["name"] or "")
            objective = st.selectbox("Цель", objective_list, index=obj_index)
            target_course = st.text_input(
                "Курс", value=camp.get("target_course") or "")
            budget = st.number_input(
                "Бюджет, ₽", min_value=0.0,
                value=float(camp.get("budget") or 0), step=1000.0)
            notes = st.text_area("Заметки", value=camp.get("notes") or "")

            b1, b2 = st.columns(2)
            save = b1.form_submit_button("💾 Сохранить", use_container_width=True)
            delete = b2.form_submit_button(
                "🗑 Удалить кампанию", use_container_width=True)

        if save:
            update_campaign(
                cid, name=name, objective=objective,
                target_course=target_course, budget=budget, notes=notes,
            )
            bust_cache()
            st.success("Сохранено")
            st.rerun()
        if delete:
            delete_campaign(cid)
            bust_cache()
            st.warning(f"Кампания `{cid}` и её размещения удалены")
            st.rerun()

    st.divider()

    # ----- Размещения -----
    st.markdown("### Размещения")
    if not placements:
        st.info("Нет размещений")
        return

    pid = st.selectbox(
        "Выбрать размещение",
        [p["placement_id"] for p in placements],
        key="edit_pl_select",
    )
    pl = next(p for p in placements if p["placement_id"] == pid)

    with st.form("edit_pl"):
        c1, c2 = st.columns(2)
        with c1:
            channel = st.text_input("Канал", value=pl["channel"] or "")
            creative_id = st.text_input("Креатив", value=pl.get("creative_id") or "")
            cost = st.number_input(
                "Стоимость, ₽", min_value=0.0,
                value=float(pl.get("cost") or 0), step=1000.0)
        with c2:
            target_course = st.text_input(
                "Курс", value=pl.get("target_course") or "")
            publication_time = st.text_input(
                "Публикация", value=pl.get("publication_time") or "")

        b1, b2 = st.columns(2)
        save_pl = b1.form_submit_button("💾 Сохранить", use_container_width=True)
        delete_pl = b2.form_submit_button(
            "🗑 Удалить размещение", use_container_width=True)

    if save_pl:
        update_placement(
            pid, channel=channel, creative_id=creative_id,
            cost=cost, target_course=target_course,
            publication_time=publication_time,
        )
        bust_cache()
        st.success("Сохранено")
        st.rerun()
    if delete_pl:
        delete_placement(pid)
        bust_cache()
        st.warning(f"Размещение `{pid}` удалено")
        st.rerun()


def _render_qr(link: str) -> None:
    if not HAS_QR:
        st.caption("QR недоступен: `pip install qrcode[pil]`")
        return
    img = qrcode.make(link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    st.image(buf.getvalue(), width=140)


def _links_section() -> None:
    placements = get_placements()
    if not placements:
        st.info("Нет размещений")
        return

    bot_username = st.text_input(
        "Bot username", value="postupashki_tracking_bot",
        help="Без @. Используется для сборки t.me/...?start=<token>")

    for p in placements:
        link = tracking.build_deeplink(bot_username, p["tracking_token"])
        with st.expander(f"{p['placement_id']} · {p['channel']}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.code(link, language="text")
                st.caption(
                    f"Креатив: {p.get('creative_id') or '—'} · "
                    f"Курс: {p.get('target_course') or '—'} · "
                    f"Cost: {float(p.get('cost') or 0):,.0f} ₽"
                )
            with c2:
                _render_qr(link)


def page_registry() -> None:
    st.title("🎯 Ad Registry")
    st.caption("Кампании, размещения и tracking-ссылки")

    t1, t2, t3, t4 = st.tabs([
        "➕ Кампания", "➕ Размещение", "✏️ Редактировать", "🔗 Tracking-ссылки",
    ])
    with t1:
        _campaign_create_form()
    with t2:
        _placement_create_form()
    with t3:
        _edit_section()
    with t4:
        _links_section()


# ============================================================
# Page: Симуляция событий
# ============================================================

def page_simulation() -> None:
    st.title("🧪 Симуляция событий")
    st.caption("Offline demo mode — не требует Telegram и интернета")

    placements = get_placements()
    if not placements:
        st.warning("Сначала создайте размещение в Ad Registry.")
        return

    # ---------- 1. Touch ----------
    with st.expander("1️⃣ Touch — переход по рекламной ссылке", expanded=True):
        with st.form("sim_touch"):
            c1, c2 = st.columns(2)
            with c1:
                tg_id = st.text_input("Telegram user id", value="1001")
                pid = st.selectbox(
                    "Размещение", [p["placement_id"] for p in placements])
            with c2:
                source = st.selectbox(
                    "Source", ["bot_deeplink", "promo_code", "self_reported"])
                conf = st.selectbox(
                    "Confidence",
                    ["deterministic", "self_reported", "modelled"])

            ok = st.form_submit_button(
                "Создать touch", use_container_width=True)

        if ok:
            uk = tracking.user_key_from_telegram_id(tg_id)
            db.ensure_user(uk)
            db.add_touch(uk, pid, source, conf)
            bust_cache()
            st.success(f"touch создан · user_key = `{uk[:12]}…`")

    # ---------- 2. Lead ----------
    with st.expander("2️⃣ Lead — заявка", expanded=False):
        with st.form("sim_lead"):
            c1, c2 = st.columns(2)
            with c1:
                tg_id_l = st.text_input(
                    "Telegram user id", value="1001", key="lead_tg")
            with c2:
                course_l = st.text_input(
                    "Курс", value="Python-разработчик", key="lead_course")

            ok = st.form_submit_button(
                "Создать лид", use_container_width=True)

        if ok:
            uk = tracking.user_key_from_telegram_id(tg_id_l)
            db.ensure_user(uk)
            lid = db.add_lead(uk, course=course_l or None)
            bust_cache()
            st.success(f"lead #{lid} создан")

    # ---------- 3. Order + Stripe ----------
    with st.expander("3️⃣ Order / payment — тестовая оплата", expanded=True):
        stripe_ok = payment.is_configured()

        if not stripe_ok:
            st.warning(
                "Stripe не настроен. Заказ будет сохранён **без реального платежа**.\n\n"
                "Для тестового платежа задайте `STRIPE_SECRET_KEY` и "
                "`STRIPE_PUBLIC_KEY` в переменных окружения "
                "или добавьте секцию `[stripe]` в `.streamlit/secrets.toml`."
            )

        with st.form("sim_order"):
            c1, c2 = st.columns(2)
            with c1:
                tg_id_o = st.text_input(
                    "Telegram user id", value="1001", key="order_tg")
                course_o = st.text_input(
                    "Курс", value="Python-разработчик", key="order_course")
            with c2:
                amount = st.number_input(
                    "Сумма, ₽", min_value=1.0, value=19_990.0, step=100.0)
                has_user = st.checkbox(
                    "У заказа есть user_key", value=True,
                    help="Снимите галочку, чтобы эмулировать заказ без tracking "
                         "— он должен остаться unknown")

            use_stripe = st.checkbox(
                "Провести через Stripe (test mode)",
                value=stripe_ok, disabled=not stripe_ok,
            )

            scenario = "success"
            if use_stripe:
                scenario = st.selectbox(
                    "Сценарий оплаты",
                    options=list(payment.TEST_SCENARIOS.keys()),
                    format_func=lambda k: payment.TEST_SCENARIOS[k]["label"],
                )
                sc = payment.TEST_SCENARIOS[scenario]
                st.caption(
                    f"Тестовая карта: `{sc['card']}` · "
                    f"ожидаемый статус: `{sc['expected']}`"
                )

            submitted = st.form_submit_button(
                "💳 Оплатить", use_container_width=True)

        if not submitted:
            return

        # --- user_key ---
        if has_user:
            uk: str | None = tracking.user_key_from_telegram_id(tg_id_o)
            db.ensure_user(uk)
        else:
            uk = None

        # --- Stripe ---
        if use_stripe:
            with st.spinner("Обработка платежа..."):
                result = payment.create_test_payment(
                    amount=amount,
                    currency="rub",
                    description=f"Курс {course_o or '—'}",
                    metadata={
                        "user_key": (uk[:16] if uk else "anonymous"),
                        "course": course_o or "",
                        "source": "streamlit_simulation",
                    },
                    scenario=scenario,
                )

            if not result.ok:
                st.error(
                    f"❌ Платёж не прошёл · статус: `{result.status}`\n\n"
                    f"{result.error or ''}"
                )
                st.info("Заказ **не сохранён** в БД.")
                return

            st.success(
                f"✅ Платёж `{result.intent_id}` прошёл · "
                f"{result.amount:.2f} {result.currency.upper()}"
            )

        # --- Save order ---
        oid = db.add_order(
            uk, course_o or None, amount,
            datetime.now().isoformat(timespec="seconds"),
            external_id=f"sim_{datetime.now():%Y%m%d_%H%M%S}",
        )
        bust_cache()
        st.success(f"order #{oid} сохранён в БД")


# ============================================================
# Page: Импорт продаж
# ============================================================

def page_sales_import() -> None:
    st.title("📥 Импорт продаж")
    st.caption("base.xlsx → transaction layer")

    st.info(
        "Исторические продажи входят с `user_key = NULL` — без tracking. "
        "Attribution engine честно помечает их как `unknown`."
    )

    uploaded = st.file_uploader("base.xlsx", type=["xlsx"])
    if uploaded is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
            f.write(uploaded.read())
            path = Path(f.name)

        if st.button("Импортировать", type="primary"):
            try:
                n = ingest_sales.ingest(path)
                bust_cache()
                st.success(f"Импортировано строк: {n}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Ошибка: {e}")

    st.divider()
    st.subheader("Текущий transaction layer")

    orders = get_orders()
    if not orders:
        st.info("Заказов пока нет.")
        return

    df = pd.DataFrame(orders)
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего заказов", len(df))
    c2.metric("Revenue", f"{df['amount'].sum():,.0f} ₽")
    if "source_file" in df.columns:
        n_from_file = int(df["source_file"].notna().sum())
        c3.metric("Из base.xlsx", f"{n_from_file} / {len(df)}")

    st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# Page: Attribution
# ============================================================

def page_attribution() -> None:
    st.title("🎯 Attribution engine")
    st.caption("deterministic → self_reported → modelled → unknown")

    window = st.slider(
        "Attribution window, дней", 1, 90, 30, key="attr_window")

    if st.button("🔁 Пересчитать attribution", type="primary"):
        summary = attribution.run_attribution(window_days=window)
        bust_cache()
        st.success(f"Готово · {summary}")

    attrs = get_attributions()
    if not attrs:
        st.info("Attribution ещё не запускался.")
        return

    df = pd.DataFrame(attrs)
    known = df[df["placement_id"].notna()]
    unknown = df[df["placement_id"].isna()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Строк", len(df))
    c2.metric("Attributed", f"{known['revenue_credit'].sum():,.0f} ₽")
    c3.metric("Unknown", f"{unknown['revenue_credit'].sum():,.0f} ₽")
    c4.metric("Методов", df["confidence"].nunique())

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Sensitivity по окну атрибуции")
    st.caption(
        "Если результат сильно меняется с окном — это важный сигнал. "
        "После запуска tracking нужно собрать реальное распределение "
        "click-to-purchase lag и выбрать окно эмпирически."
    )

    if st.button("📐 Посчитать 7 / 14 / 30 дней"):
        with st.spinner("Считаем..."):
            res = romi.run_attribution_with_sensitivity((7, 14, 30))
        bust_cache()

        sens_df = pd.DataFrame([
            {"window_days": w,
             "attributed_revenue": v["attributed_revenue"],
             "unknown_revenue": v["unknown_revenue"]}
            for w, v in res.items()
        ])
        st.dataframe(sens_df, use_container_width=True, hide_index=True)


# ============================================================
# Page: ROMI
# ============================================================

def page_romi() -> None:
    st.title("💰 ROMI")

    window = st.slider(
        "Attribution window, дней", 1, 90, 30, key="romi_window")

    if st.button("🔁 Пересчитать ROMI", type="primary"):
        attribution.run_attribution(window_days=window)
        bust_cache()
        st.rerun()

    df, unknown_df = romi.build_romi_table(window_days=window)

    st.subheader("По размещениям")
    if df.empty:
        st.info("Нет данных. Создайте размещения и заказы.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Unknown — не приписано рекламе")
    if unknown_df.empty:
        st.success("Все заказы имеют атрибуцию.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Revenue без атрибуции",
                  f"{unknown_df['revenue'].sum():,.0f} ₽")
        c2.metric("Заказов без атрибуции", len(unknown_df))
        st.dataframe(unknown_df, use_container_width=True, hide_index=True)

    # ---------- Excel export ----------
    if not df.empty or not unknown_df.empty:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            if not df.empty:
                df.to_excel(writer, sheet_name="placements", index=False)
            if not unknown_df.empty:
                unknown_df.to_excel(writer, sheet_name="unknown", index=False)

        st.download_button(
            "⬇️ Скачать ROMI .xlsx",
            data=buf.getvalue(),
            file_name=f"romi_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime=("application/vnd.openxmlformats-officedocument"
                  ".spreadsheetml.sheet"),
            use_container_width=True,
        )

    st.warning(
        "ROMI считается на **revenue**. Для production decision нужен "
        "**contribution margin**. Пока это верхняя оценка."
    )


# ============================================================
# Router
# ============================================================

with st.sidebar:
    st.header("Поступашки · Measurement")
    page = st.radio("Раздел", PAGES, label_visibility="collapsed")
    st.divider()

    if payment.is_configured():
        st.success("Stripe: подключён (test)", icon="💳")
    else:
        st.warning("Stripe: не настроен", icon="💳")

    if HAS_QR:
        st.caption("QR: доступен")
    else:
        st.caption("QR: `pip install qrcode[pil]`")


if page == "Обзор":
    page_overview()
elif page == "Ad Registry":
    page_registry()
elif page == "Симуляция событий":
    page_simulation()
elif page == "Импорт продаж":
    page_sales_import()
elif page == "Attribution":
    page_attribution()
elif page == "ROMI":
    page_romi()