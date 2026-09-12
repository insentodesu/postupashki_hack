from datetime import datetime
import pandas as pd
import streamlit as st

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

import db
import tracking
import attribution
import romi
import seed_demo
import ingest_sales

st.set_page_config(page_title="Поступашки · Measurement", layout="wide")
db.init_db()

PAGES = ["Обзор", "Ad Registry", "Симуляция событий",
         "Импорт продаж", "Attribution", "ROMI"]


# ---------------- Обзор ----------------
def page_overview():
    st.title("Measurement platform — обзор")
    st.caption("campaign → placement → touch → lead → order → revenue → ROMI")

    campaigns = db.list_campaigns()
    placements = db.list_placements()
    touches = db.list_touches()
    leads = db.list_leads()
    orders = db.list_orders()
    attrs = db.list_attributions()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Кампании", len(campaigns))
    c2.metric("Размещения", len(placements))
    c3.metric("Touches", len(touches))
    c4.metric("Заказы", len(orders))

    total_rev = sum(o["amount"] for o in orders)
    known_rev = sum(a["revenue_credit"] for a in attrs if a["placement_id"])
    unknown_rev = sum(a["revenue_credit"] for a in attrs if not a["placement_id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue (всего)", f"{total_rev:,.0f} ₽")
    c2.metric("Attributed", f"{known_rev:,.0f} ₽")
    c3.metric("Unknown", f"{unknown_rev:,.0f} ₽")

    st.info("Unknown — заказы без tracking. Мы не приписываем их рекламе.")

    if st.button("🌱 Загрузить демо-данные"):
        seed_demo.seed()
        st.success("Демо загружено.")
        st.rerun()

    st.subheader("Воронка")
    st.write({"touches": len(touches), "leads": len(leads), "orders": len(orders)})


# ---------------- Ad Registry ----------------
def page_registry():
    st.title("Ad Registry")
    st.caption("Кампания / размещение / tracking-ссылка")

    tab1, tab2 = st.tabs(["Кампания", "Размещение"])

    with tab1:
        with st.form("campaign_form"):
            cid = st.text_input("campaign_id", value=f"camp_{datetime.now():%Y%m%d}")
            name = st.text_input("Название")
            objective = st.selectbox("Цель", ["Awareness", "Traffic", "Leads", "Sales"])
            target_course = st.text_input("Целевой курс")
            budget = st.number_input("Бюджет, ₽", min_value=0.0, value=100000.0)
            start_date = st.date_input("Дата начала")
            end_date = st.date_input("Дата окончания")
            notes = st.text_area("Заметки")
            if st.form_submit_button("Создать кампанию"):
                try:
                    db.create_campaign(cid, name, objective, target_course,
                                       str(start_date), str(end_date), budget, notes)
                    st.success(f"Кампания {cid} создана")
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    with tab2:
        campaigns = db.list_campaigns()
        if not campaigns:
            st.warning("Сначала создайте кампанию.")
            return
        with st.form("placement_form"):
            pid = st.text_input("placement_id", value=f"pl_{datetime.now():%H%M%S}")
            campaign_id = st.selectbox("Кампания", [c["campaign_id"] for c in campaigns])
            channel = st.text_input("Канал", value="@channel_x")
            creative_id = st.text_input("Креатив", value="creative_01")
            cost = st.number_input("Стоимость, ₽", min_value=0.0, value=10000.0)
            publication_time = st.text_input(
                "Время публикации (ISO)",
                value=datetime.now().isoformat(timespec="seconds"))
            target_course = st.text_input("Курс", value="Python-разработчик")
            token = st.text_input("Tracking token", value=tracking.new_tracking_token())
            if st.form_submit_button("Создать размещение"):
                try:
                    db.create_placement(pid, campaign_id, channel, creative_id,
                                        cost, publication_time, target_course, token)
                    st.success("Размещение создано")
                except Exception as e:
                    st.error(f"Ошибка: {e}")

        st.subheader("Tracking-ссылки")
        bot_username = st.text_input("Bot username",
                                     value="postupashki_tracking_bot")
        for p in db.list_placements():
            link = tracking.build_deeplink(bot_username, p["tracking_token"])
            st.code(f"{p['placement_id']} | {p['channel']} → {link}", language="text")


# ---------------- Симуляция событий ----------------
def page_simulation():
    st.title("Симуляция событий")
    st.caption("Offline demo mode — без Telegram и интернета")

    placements = db.list_placements()
    if not placements:
        st.warning("Сначала создайте размещение в Ad Registry.")
        return

    st.subheader("1. Touch (переход по ссылке)")
    with st.form("sim_touch"):
        tg_id = st.text_input("Telegram user id", value="1001")
        pid = st.selectbox("Размещение", [p["placement_id"] for p in placements])
        source = st.selectbox("Source", ["bot_deeplink", "promo_code", "self_reported"])
        conf = st.selectbox("Confidence",
                            ["deterministic", "self_reported", "modelled"])
        if st.form_submit_button("Создать touch"):
            uk = tracking.user_key_from_telegram_id(tg_id)
            db.ensure_user(uk)
            db.add_touch(uk, pid, source, conf)
            st.success(f"touch создан, user_key = {uk[:8]}…")

    st.subheader("2. Lead")
    with st.form("sim_lead"):
        tg_id = st.text_input("Telegram user id", value="1001", key="lead_tg")
        course = st.text_input("Курс", value="Python-разработчик")
        if st.form_submit_button("Создать лид"):
            uk = tracking.user_key_from_telegram_id(tg_id)
            db.ensure_user(uk)
            lid = db.add_lead(uk, course=course)
            st.success(f"lead #{lid} создан")

    st.subheader("3. Order / payment")
    with st.form("sim_order"):
        tg_id = st.text_input("Telegram user id", value="1001", key="order_tg")
        course = st.text_input("Курс", value="Python-разработчик", key="order_course")
        amount = st.number_input("Сумма, ₽", min_value=0.0, value=19990.0)
        ts = st.text_input("Время (ISO)",
                           value=datetime.now().isoformat(timespec="seconds"))
        has_user = st.checkbox("У заказа есть user_key", value=True)
        if st.form_submit_button("Добавить оплату"):
            if has_user:
                uk = tracking.user_key_from_telegram_id(tg_id)
                db.ensure_user(uk)
            else:
                uk = None
            oid = db.add_order(uk, course, amount, ts,
                               external_id=f"sim_{datetime.now():%H%M%S}")
            st.success(f"order #{oid} добавлен")


# ---------------- Импорт продаж ----------------
def page_sales_import():
    st.title("Импорт продаж")
    st.caption("base.xlsx → transaction layer. Атрибуцию НЕ придумываем.")

    st.markdown("Исторические продажи входят с `user_key = NULL`. "
                "Attribution engine честно помечает их как `unknown`.")

    uploaded = st.file_uploader("base.xlsx", type=["xlsx"])
    if uploaded is not None:
        import tempfile, pathlib
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f:
            f.write(uploaded.read())
            path = pathlib.Path(f.name)
        try:
            n = ingest_sales.ingest(path)
            st.success(f"Импортировано строк: {n}")
        except Exception as e:
            st.error(f"Ошибка: {e}")

    st.subheader("Текущий transaction layer")
    orders = db.list_orders()
    if orders:
        st.dataframe(pd.DataFrame(orders), use_container_width=True)
    else:
        st.info("Заказов пока нет.")


# ---------------- Attribution ----------------
def page_attribution():
    st.title("Attribution engine")
    st.caption("deterministic → self_reported → modelled → unknown")

    window = st.slider("Attribution window, дней", 1, 90, 30)
    if st.button("Пересчитать attribution"):
        summary = attribution.run_attribution(window_days=window)
        st.success(f"Готово: {summary}")

    attrs = db.list_attributions()
    if not attrs:
        st.info("Attribution ещё не запускался.")
        return

    st.dataframe(pd.DataFrame(attrs), use_container_width=True)

    st.subheader("Sensitivity: окно атрибуции")
    if st.button("Посчитать sensitivity по окнам 7 / 14 / 30"):
        with st.spinner("Считаем..."):
            res = romi.run_attribution_with_sensitivity((7, 14, 30))
        st.json(res)


# ---------------- ROMI ----------------
def page_romi():
    st.title("ROMI")

    window = st.slider("Attribution window, дней", 1, 90, 30, key="romi_window")
    if st.button("Пересчитать ROMI"):
        attribution.run_attribution(window_days=window)
        st.rerun()

    df, unknown_df = romi.build_romi_table(window_days=window)

    st.subheader("По размещениям")
    st.dataframe(df, use_container_width=True)

    st.subheader("Unknown — не приписано рекламе")
    if unknown_df.empty:
        st.info("Все заказы имеют атрибуцию.")
    else:
        st.dataframe(unknown_df, use_container_width=True)
        st.metric("Revenue без атрибуции",
                  f"{unknown_df['revenue'].sum():,.0f} ₽")

    st.warning("ROMI считается на revenue. Для production decision нужен "
               "contribution margin. Пока это верхняя оценка.")


# ---------------- Router ----------------
with st.sidebar:
    st.header("Поступашки · Measurement")
    page = st.radio("Раздел", PAGES)

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