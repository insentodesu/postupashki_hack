# Data Dictionary — Postupashki Measurement System

> Физические имена таблиц и колонок оставлены на английском для совместимости с PostgreSQL, Python, BI и интеграциями. Русские названия ниже описывают бизнес-смысл.

## Сквозной процесс

`campaign -> marketing_activity -> touch -> user -> lead -> order -> order_item`

Атрибуция: `touch + order -> attribution -> ROMI_attr`

Инкрементальность: `experiment / causal model -> incrementality_estimate -> ROMI_inc`

## Таблицы

| Таблица | Русское название | Одна строка означает | Основной источник / процесс |
|---|---|---|---|
| `users` | Пользователи | одного внутреннего пользователя системы | base.xlsx / future tracking |
| `user_identities` | Идентификаторы пользователей | один внешний ID пользователя | student_id / telegram_hash / CRM |
| `courses` | Курсы | один продукт | base.xlsx / справочник |
| `campaigns` | Кампании | одну маркетинговую кампанию | reconstructed history / ad registry |
| `marketing_activities` | Маркетинговые активности | один пост или рекламное размещение | TGStat / Telegram / ad registry |
| `activity_metric_snapshots` | Снимки метрик | состояние метрик поста в момент времени | TGStat / collector |
| `touches` | Касания | одно user-level касание с рекламой | tracking bot / deep link |
| `leads` | Лиды | один коммерческий интерес / handoff менеджеру | tracking/manager flow |
| `orders` | Заказы | один платёж/заказ | base.xlsx / future sales flow |
| `order_items` | Позиции заказа | один курс внутри заказа | base.xlsx |
| `attributions` | Атрибуции | долю заказа, приписанную одному touch | attribution engine |
| `incrementality_estimates` | Оценки инкрементальности | одну causal-оценку эффекта | A/B, holdout, DiD, ITS и др. |

## Ключевые бизнес-оговорки

### Исторические продажи
В исходных данных нет настоящего `order_id`. Рабочая реконструкция заказа: одинаковые `student_id + timestamp` считаются одним заказом. Поэтому исторический `orders.data_origin = reconstructed`, а правило хранится в `reconstruction_method`.

### Bundle-покупки
`order_items.source_amount` сохраняет исходный `amount`, но не называется `course_revenue`, потому что при пакетных покупках это не обязательно реальная самостоятельная цена каждого курса.

### Исторический user stitching
Обезличенный `student_id` позволяет различать покупателей внутри sales dataset, но не позволяет надежно сопоставить их с конкретными Telegram-пользователями или просмотрами TGStat.

### Future user stitching
Для новых запусков целевой deterministic flow:

`tracking_code -> bot/deep-link -> telegram user -> hashed identity -> user_id -> lead_id -> order`

Это позволяет связать рекламную активность с оплатой без хранения лишних персональных данных.

### Aggregated Telegram metrics
`views`, `likes`, `reposts` — агрегатные метрики публикации. Они не означают, что мы знаем, какой конкретно пользователь видел пост.

### Attribution != Incrementality
`attributions` отвечает на вопрос «какому касанию распределить случившуюся выручку».

`incrementality_estimates` отвечает на вопрос «сколько продаж/выручки появилось именно благодаря маркетинговому воздействию».

### Data origin
- `observed` — непосредственно наблюдается в источнике;
- `reconstructed` — восстановлено по принятому правилу или публичной истории;
- `synthetic` — создано для демонстрации MVP.

Это разделение обязательно сохранять во всех загрузочных скриптах и аналитике.
