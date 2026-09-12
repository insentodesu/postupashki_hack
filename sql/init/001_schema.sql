-- Postupashki marketing measurement system
-- PostgreSQL schema v1

BEGIN;

CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic'))
);

CREATE TABLE user_identities (
    identity_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id)
        ON DELETE CASCADE,
    identity_type TEXT NOT NULL,
    identity_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    UNIQUE (identity_type, identity_value)
);

CREATE TABLE courses (
    course_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE campaigns (
    campaign_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_key TEXT UNIQUE,
    campaign_name TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    description TEXT,
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        ended_at IS NULL
        OR started_at IS NULL
        OR ended_at >= started_at
    )
);

CREATE TABLE marketing_activities (
    activity_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id BIGINT
        REFERENCES campaigns(campaign_id)
        ON DELETE SET NULL,
    course_id BIGINT
        REFERENCES courses(course_id)
        ON DELETE SET NULL,
    activity_type TEXT NOT NULL,
    channel_name TEXT,
    published_at TIMESTAMPTZ,
    cost NUMERIC(12, 2)
        CHECK (cost >= 0),
    discount_pct NUMERIC(5, 2)
        CHECK (discount_pct >= 0 AND discount_pct <= 100),
    tracking_code TEXT UNIQUE,
    summary TEXT,
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE activity_metric_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    activity_id BIGINT NOT NULL
        REFERENCES marketing_activities(activity_id)
        ON DELETE CASCADE,
    collected_at TIMESTAMPTZ NOT NULL,
    views BIGINT CHECK (views >= 0),
    reposts BIGINT CHECK (reposts >= 0),
    comments BIGINT CHECK (comments >= 0),
    likes BIGINT CHECK (likes >= 0),
    clicks_fwd BIGINT CHECK (clicks_fwd >= 0),
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    UNIQUE (activity_id, collected_at)
);

CREATE TABLE touches (
    touch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id)
        ON DELETE CASCADE,
    activity_id BIGINT
        REFERENCES marketing_activities(activity_id)
        ON DELETE CASCADE,
    touched_at TIMESTAMPTZ NOT NULL,
    touch_type TEXT NOT NULL,
    tracking_method TEXT NOT NULL,
    confidence NUMERIC(4, 3)
        CHECK (confidence >= 0 AND confidence <= 1),
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE leads (
    lead_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id)
        ON DELETE CASCADE,
    course_id BIGINT
        REFERENCES courses(course_id)
        ON DELETE SET NULL,
    source_touch_id BIGINT
        REFERENCES touches(touch_id)
        ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'new',
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES users(user_id),
    lead_id BIGINT
        REFERENCES leads(lead_id)
        ON DELETE SET NULL,
    ordered_at TIMESTAMPTZ NOT NULL,
    revenue NUMERIC(12, 2) NOT NULL
        CHECK (revenue >= 0),
    source_order_key TEXT UNIQUE,
    reconstruction_method TEXT,
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_items (
    order_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,
    course_id BIGINT NOT NULL
        REFERENCES courses(course_id),
    source_amount NUMERIC(12, 2)
        CHECK (source_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE attributions (
    attribution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,
    touch_id BIGINT NOT NULL
        REFERENCES touches(touch_id)
        ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    attribution_weight NUMERIC(6, 5) NOT NULL
        CHECK (attribution_weight >= 0 AND attribution_weight <= 1),
    attributed_revenue NUMERIC(12, 2) NOT NULL
        CHECK (attributed_revenue >= 0),
    attribution_window_days INTEGER
        CHECK (attribution_window_days > 0),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, touch_id, model_name)
);

CREATE TABLE incrementality_estimates (
    estimate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id BIGINT
        REFERENCES campaigns(campaign_id)
        ON DELETE CASCADE,
    activity_id BIGINT
        REFERENCES marketing_activities(activity_id)
        ON DELETE CASCADE,
    method TEXT NOT NULL,
    observed_revenue NUMERIC(12, 2)
        CHECK (observed_revenue >= 0),
    counterfactual_revenue NUMERIC(12, 2)
        CHECK (counterfactual_revenue >= 0),
    incremental_revenue NUMERIC(12, 2),
    incremental_orders NUMERIC(12, 2),
    ci_lower NUMERIC(12, 2),
    ci_upper NUMERIC(12, 2),
    data_origin TEXT NOT NULL
        CHECK (data_origin IN ('observed', 'reconstructed', 'synthetic')),
    estimated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (num_nonnulls(campaign_id, activity_id) = 1),
    CHECK (
        ci_lower IS NULL
        OR ci_upper IS NULL
        OR ci_lower <= ci_upper
    )
);

CREATE INDEX idx_user_identities_user_id
    ON user_identities(user_id);

CREATE INDEX idx_marketing_activities_campaign_id
    ON marketing_activities(campaign_id);

CREATE INDEX idx_marketing_activities_course_id
    ON marketing_activities(course_id);

CREATE INDEX idx_marketing_activities_published_at
    ON marketing_activities(published_at);

CREATE INDEX idx_activity_metric_snapshots_activity_id
    ON activity_metric_snapshots(activity_id);

CREATE INDEX idx_touches_user_id
    ON touches(user_id);

CREATE INDEX idx_touches_activity_id
    ON touches(activity_id);

CREATE INDEX idx_touches_touched_at
    ON touches(touched_at);

CREATE INDEX idx_leads_user_id
    ON leads(user_id);

CREATE INDEX idx_leads_source_touch_id
    ON leads(source_touch_id);

CREATE INDEX idx_orders_user_id
    ON orders(user_id);

CREATE INDEX idx_orders_lead_id
    ON orders(lead_id);

CREATE INDEX idx_orders_ordered_at
    ON orders(ordered_at);

CREATE INDEX idx_order_items_order_id
    ON order_items(order_id);

CREATE INDEX idx_attributions_order_id
    ON attributions(order_id);

CREATE INDEX idx_attributions_touch_id
    ON attributions(touch_id);

CREATE INDEX idx_attributions_model_name
    ON attributions(model_name);


-- ============================================================
-- БИЗНЕС-КОММЕНТАРИИ И DATA DICTIONARY ВНУТРИ POSTGRESQL
-- Физические имена таблиц/полей оставлены на английском для
-- совместимости с Python, SQL, BI и другими компонентами MVP.
-- Русские бизнес-наименования и смысл доступны через COMMENT ON.
-- ============================================================

COMMENT ON TABLE users IS
'Пользователи. Одна строка = один внутренний пользователь measurement system. Это системная сущность, объединяющая идентификаторы одного человека из разных источников.';

COMMENT ON COLUMN users.user_id IS
'Внутренний ID пользователя. Не является Telegram ID или исходным student_id.';
COMMENT ON COLUMN users.created_at IS
'Дата и время появления пользователя в нашей системе.';
COMMENT ON COLUMN users.data_origin IS
'Происхождение записи: observed — наблюдаемая, reconstructed — восстановленная, synthetic — синтетическая.';

COMMENT ON TABLE user_identities IS
'Идентификаторы пользователя во внешних системах. Нужны для user stitching: один users.user_id может иметь legacy student_id, telegram_hash, CRM ID и другие идентификаторы.';

COMMENT ON COLUMN user_identities.identity_id IS
'Внутренний ID записи идентификатора.';
COMMENT ON COLUMN user_identities.user_id IS
'Ссылка на единого внутреннего пользователя.';
COMMENT ON COLUMN user_identities.identity_type IS
'Тип внешнего идентификатора, например legacy_student_id, telegram_hash, crm_id.';
COMMENT ON COLUMN user_identities.identity_value IS
'Значение внешнего идентификатора. Для Telegram рекомендуется хранить хеш/HMAC, а не открытый ID.';
COMMENT ON COLUMN user_identities.created_at IS
'Когда идентификатор был добавлен в систему.';
COMMENT ON COLUMN user_identities.data_origin IS
'Происхождение идентификатора: observed / reconstructed / synthetic.';

COMMENT ON TABLE courses IS
'Справочник курсов/продуктов. Используется единообразно в продажах, лидах и маркетинговых активностях.';

COMMENT ON COLUMN courses.course_id IS
'Внутренний ID курса.';
COMMENT ON COLUMN courses.course_name IS
'Название курса/продукта.';
COMMENT ON COLUMN courses.created_at IS
'Когда курс появился в справочнике.';

COMMENT ON TABLE campaigns IS
'Маркетинговые кампании верхнего уровня. Кампания может включать несколько постов, внешних размещений, скидочных сообщений и других активностей.';

COMMENT ON COLUMN campaigns.campaign_id IS
'Внутренний ID кампании.';
COMMENT ON COLUMN campaigns.campaign_key IS
'Технический ключ кампании, например pro_launch_sep26. Используется для интеграций и загрузки данных.';
COMMENT ON COLUMN campaigns.campaign_name IS
'Человекочитаемое название кампании.';
COMMENT ON COLUMN campaigns.started_at IS
'Дата/время начала кампании, если известно.';
COMMENT ON COLUMN campaigns.ended_at IS
'Дата/время окончания кампании, если известно.';
COMMENT ON COLUMN campaigns.description IS
'Краткое описание цели или механики кампании.';
COMMENT ON COLUMN campaigns.data_origin IS
'Происхождение кампании. Для исторически восстановленных кампаний обычно reconstructed.';
COMMENT ON COLUMN campaigns.created_at IS
'Когда запись кампании была создана в БД.';

COMMENT ON TABLE marketing_activities IS
'Конкретные маркетинговые активности. Одна строка = один пост, рекламное размещение, launch, скидочная публикация, native-интеграция и т.п. Исторические TGStat-посты и будущие платные размещения живут в одной сущности.';

COMMENT ON COLUMN marketing_activities.activity_id IS
'Внутренний ID конкретной маркетинговой активности.';
COMMENT ON COLUMN marketing_activities.campaign_id IS
'Кампания, к которой относится активность. Может быть NULL для отдельного контентного поста без кампании.';
COMMENT ON COLUMN marketing_activities.course_id IS
'Продвигаемый курс, если активность относится к конкретному продукту.';
COMMENT ON COLUMN marketing_activities.activity_type IS
'Тип активности, например owned_post, external_ad, launch_post, sale_post, native, educational.';
COMMENT ON COLUMN marketing_activities.channel_name IS
'Telegram-канал или другая площадка, где размещена активность.';
COMMENT ON COLUMN marketing_activities.published_at IS
'Фактическое или восстановленное время публикации/размещения.';
COMMENT ON COLUMN marketing_activities.cost IS
'Стоимость конкретного размещения/активности. Без этого поля ROMI по платной рекламе не рассчитывается.';
COMMENT ON COLUMN marketing_activities.discount_pct IS
'Размер скидки в процентах, если активность содержала скидочное предложение.';
COMMENT ON COLUMN marketing_activities.tracking_code IS
'Уникальный код будущего трекинга, например код deep-link для Telegram-бота. Позволяет детерминированно связать касание с активностью.';
COMMENT ON COLUMN marketing_activities.summary IS
'Краткое описание содержания или оффера.';
COMMENT ON COLUMN marketing_activities.data_origin IS
'Происхождение данных: observed / reconstructed / synthetic.';
COMMENT ON COLUMN marketing_activities.created_at IS
'Когда активность была записана в БД.';

COMMENT ON TABLE activity_metric_snapshots IS
'Снимки агрегатных метрик маркетинговых активностей во времени. Отдельная таблица нужна потому, что views/likes/reposts могут расти после публикации. Эти метрики НЕ являются user-level tracking.';

COMMENT ON COLUMN activity_metric_snapshots.snapshot_id IS
'ID снимка метрик.';
COMMENT ON COLUMN activity_metric_snapshots.activity_id IS
'Маркетинговая активность, для которой собраны метрики.';
COMMENT ON COLUMN activity_metric_snapshots.collected_at IS
'Когда был сделан снимок метрик.';
COMMENT ON COLUMN activity_metric_snapshots.views IS
'Количество просмотров на момент снимка.';
COMMENT ON COLUMN activity_metric_snapshots.reposts IS
'Количество репостов на момент снимка.';
COMMENT ON COLUMN activity_metric_snapshots.comments IS
'Количество комментариев на момент снимка.';
COMMENT ON COLUMN activity_metric_snapshots.likes IS
'Количество реакций/лайков на момент снимка.';
COMMENT ON COLUMN activity_metric_snapshots.clicks_fwd IS
'Доступная агрегатная метрика переходов/forward clicks из источника данных, если она есть.';
COMMENT ON COLUMN activity_metric_snapshots.data_origin IS
'Происхождение снимка: observed / reconstructed / synthetic.';

COMMENT ON TABLE touches IS
'Пользовательские маркетинговые касания. Одна строка = наблюдаемое или моделируемое соприкосновение конкретного пользователя с конкретной активностью. Это центральный мост между маркетингом и пользователем.';

COMMENT ON COLUMN touches.touch_id IS
'Внутренний ID касания.';
COMMENT ON COLUMN touches.user_id IS
'Пользователь, совершивший касание.';
COMMENT ON COLUMN touches.activity_id IS
'Маркетинговая активность, с которой произошло касание.';
COMMENT ON COLUMN touches.touched_at IS
'Время касания.';
COMMENT ON COLUMN touches.touch_type IS
'Тип касания: bot_start, tracking_link_click, CTA_click и т.п.';
COMMENT ON COLUMN touches.tracking_method IS
'Как установлена связь: deterministic, self_reported, modelled и т.п.';
COMMENT ON COLUMN touches.confidence IS
'Уверенность в связи от 0 до 1. Для deterministic обычно 1.0.';
COMMENT ON COLUMN touches.data_origin IS
'Происхождение касания: observed / reconstructed / synthetic.';
COMMENT ON COLUMN touches.created_at IS
'Когда касание записано в БД.';

COMMENT ON TABLE leads IS
'Лиды. Одна строка = один зафиксированный коммерческий интерес или передача пользователя менеджеру. Лид соединяет маркетинговое касание и дальнейшую продажу.';

COMMENT ON COLUMN leads.lead_id IS
'Внутренний ID лида. Может передаваться менеджеру/в систему продаж для deterministic stitching.';
COMMENT ON COLUMN leads.user_id IS
'Пользователь, проявивший коммерческий интерес.';
COMMENT ON COLUMN leads.course_id IS
'Курс, которым интересуется пользователь.';
COMMENT ON COLUMN leads.source_touch_id IS
'Маркетинговое касание, из которого возник лид, если оно известно.';
COMMENT ON COLUMN leads.status IS
'Статус лида, например new, contacted, qualified, converted, lost.';
COMMENT ON COLUMN leads.data_origin IS
'Происхождение лида: observed / reconstructed / synthetic.';
COMMENT ON COLUMN leads.created_at IS
'Когда лид появился в системе.';

COMMENT ON TABLE orders IS
'Заказы/платежи. Для исторического base.xlsx order_id отсутствует, поэтому заказ реконструируется по принятому правилу. Для будущих запусков заказ желательно связывать с lead_id.';

COMMENT ON COLUMN orders.order_id IS
'Внутренний ID заказа.';
COMMENT ON COLUMN orders.user_id IS
'Покупатель.';
COMMENT ON COLUMN orders.lead_id IS
'Лид, который привёл к заказу. Для исторических заказов обычно NULL.';
COMMENT ON COLUMN orders.ordered_at IS
'Время покупки/оплаты. В исходном кейсе соответствует времени выдачи доступа к курсу.';
COMMENT ON COLUMN orders.revenue IS
'Общая выручка по заказу. Для исторического reconstructed order считается как сумма amount строк внутри заказа.';
COMMENT ON COLUMN orders.source_order_key IS
'Технический ключ исходного/реконструированного заказа. Нужен для идемпотентной загрузки и защиты от дублей.';
COMMENT ON COLUMN orders.reconstruction_method IS
'Правило восстановления заказа. Для base.xlsx рабочая гипотеза: same_student_same_timestamp.';
COMMENT ON COLUMN orders.data_origin IS
'Происхождение заказа. Исторически реконструированные заказы должны маркироваться reconstructed.';
COMMENT ON COLUMN orders.created_at IS
'Когда заказ записан в БД.';

COMMENT ON TABLE order_items IS
'Позиции заказа. Одна строка = один курс внутри заказа. Нужны для корректного представления bundle-покупок.';

COMMENT ON COLUMN order_items.order_item_id IS
'ID позиции заказа.';
COMMENT ON COLUMN order_items.order_id IS
'Заказ, в который входит позиция.';
COMMENT ON COLUMN order_items.course_id IS
'Курс внутри заказа.';
COMMENT ON COLUMN order_items.source_amount IS
'Значение amount из исходной строки. В bundle не интерпретируется как достоверная самостоятельная цена курса.';
COMMENT ON COLUMN order_items.created_at IS
'Когда позиция заказа записана в БД.';

COMMENT ON TABLE attributions IS
'Результаты attribution model. Одна строка = доля выручки конкретного заказа, приписанная конкретному касанию в рамках конкретной модели. Attribution распределяет уже случившуюся выручку и НЕ доказывает причинный эффект рекламы.';

COMMENT ON COLUMN attributions.attribution_id IS
'ID результата атрибуции.';
COMMENT ON COLUMN attributions.order_id IS
'Заказ, выручка которого распределяется.';
COMMENT ON COLUMN attributions.touch_id IS
'Касание, которому приписана часть выручки.';
COMMENT ON COLUMN attributions.model_name IS
'Название модели: last_touch, first_touch, linear, time_decay и т.п.';
COMMENT ON COLUMN attributions.attribution_weight IS
'Доля выручки заказа, присвоенная этому касанию, от 0 до 1.';
COMMENT ON COLUMN attributions.attributed_revenue IS
'Сумма выручки, приписанная касанию выбранной моделью.';
COMMENT ON COLUMN attributions.attribution_window_days IS
'Окно атрибуции в днях. Должно быть обосновано и желательно проверяться sensitivity analysis.';
COMMENT ON COLUMN attributions.calculated_at IS
'Когда была рассчитана атрибуция.';

COMMENT ON TABLE incrementality_estimates IS
'Оценки причинного эффекта рекламы. Хранятся отдельно от attribution. Одна строка = causal-оценка на уровне кампании ИЛИ активности, например holdout, A/B, DiD, ITS.';

COMMENT ON COLUMN incrementality_estimates.estimate_id IS
'ID causal-оценки.';
COMMENT ON COLUMN incrementality_estimates.campaign_id IS
'Кампания, для которой оценён causal effect. Заполняется либо campaign_id, либо activity_id.';
COMMENT ON COLUMN incrementality_estimates.activity_id IS
'Конкретная активность, для которой оценён causal effect. Заполняется либо activity_id, либо campaign_id.';
COMMENT ON COLUMN incrementality_estimates.method IS
'Метод оценки: holdout, ab_test, did, synthetic_control, its и т.п.';
COMMENT ON COLUMN incrementality_estimates.observed_revenue IS
'Фактически наблюдаемая выручка в анализируемой группе/периоде.';
COMMENT ON COLUMN incrementality_estimates.counterfactual_revenue IS
'Оценка выручки, которая была бы без рекламного воздействия.';
COMMENT ON COLUMN incrementality_estimates.incremental_revenue IS
'Дополнительная выручка, причинно связанная с воздействием по выбранному дизайну/модели.';
COMMENT ON COLUMN incrementality_estimates.incremental_orders IS
'Оценка дополнительного количества заказов.';
COMMENT ON COLUMN incrementality_estimates.ci_lower IS
'Нижняя граница доверительного интервала causal effect.';
COMMENT ON COLUMN incrementality_estimates.ci_upper IS
'Верхняя граница доверительного интервала causal effect.';
COMMENT ON COLUMN incrementality_estimates.data_origin IS
'Происхождение оценки. Для demo на mock-эксперименте — synthetic.';
COMMENT ON COLUMN incrementality_estimates.estimated_at IS
'Когда была рассчитана causal-оценка.';

-- ============================================================
-- КЛЮЧЕВАЯ БИЗНЕС-ЛОГИКА СХЕМЫ
--
-- 1) Исторические продажи:
--    base.xlsx -> users/user_identities -> reconstructed orders -> order_items.
--    Исторические student_id позволяют группировать покупки одного покупателя
--    внутри датасета, но не позволяют надежно сшить его с Telegram-пользователем.
--
-- 2) Исторический маркетинг:
--    TGStat/public Telegram -> campaigns + marketing_activities
--    + activity_metric_snapshots.
--    Агрегатные views/reposts не дают user-level связи с покупателями.
--
-- 3) Будущий deterministic tracking:
--    campaign -> marketing_activity(tracking_code)
--    -> bot/deep-link -> touch -> user -> lead -> order.
--
-- 4) Attribution:
--    touches + orders -> attributions -> ROMI_attr.
--    Несколько моделей могут существовать одновременно; аналитические VIEW
--    должны обязательно фильтровать/группировать по model_name.
--
-- 5) Incrementality:
--    эксперимент/causal design -> incrementality_estimates -> ROMI_inc.
--    Incrementality не должна смешиваться с attribution.
--
-- 6) data_origin:
--    observed      = непосредственно наблюдаем в источнике;
--    reconstructed = восстановили по правилу/публичной истории;
--    synthetic     = создали для демонстрации MVP.
--
-- Это принципиально для кейса: неопределённость не маскируется моделью.
-- ============================================================

COMMIT;
