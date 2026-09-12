# Marketing Measurement Platform (MVP)

**Решение для прозрачной оценки эффективности рекламы: от клика до выручки и ROMI.**

## О проекте
Мы не пытаемся угадать, какая реклама сработала в прошлом. Вместо этого мы создаем работающую систему измерения, которая со следующего запуска начинает связывать рекламу → пользователя → лид → оплату → деньги. 

**Главная цель:** Ответить на бизнес-вопрос — куда положить следующие 300 000 ₽, чтобы каждый вложенный рубль приносил больше денег.

## Архитектура и принцип работы
В основе решения — небольшая end-to-end цепочка:
`campaign → placement → creative → touch → lead → order → revenue → ROMI`

### Компоненты системы:
*   **Ad Registry** — создание кампаний и размещений (канал, креатив, стоимость, дата). Генерация уникальных Telegram deep links.
*   **Tracking Bot** — фиксирует переход по ссылке, хеширует Telegram ID, создает касание (touch) и лид.
*   **Payment Adapter** — импорт исторических продаж (`base.xlsx`) и добавление тестовых оплат.
*   **Attribution Engine** — связывает оплату с рекламным касанием (по умолчанию: last eligible touch, окно 30 дней).
*   **ROMI Engine** — считает расходы, выручку, CAC и ROMI. Если переменных затрат нет, используем revenue-based ROMI.
*   **Dashboard** — отображает воронку, результаты по размещениям и уровень достоверности данных.

## Ключевой принцип: Честность данных
Мы не скрываем неопределенность. Каждому касанию присваивается метод атрибуции и уровень надежности:

| Ситуация | Метод атрибуции | Надежность |
| :--- | :--- | :--- |
| Переход по уникальной ссылке (bot deep link) | `deterministic` | Высокая |
| Сам указал источник менеджеру | `self-reported` | Средняя |
| Известный пост перед покупкой | `modelled` | Низкая/Средняя |
| Нет информации | `organic / unknown` | Неизвестно |

*Если точную связь построить нельзя (например, человек просто читал канал и написал менеджеру), мы не пытаемся угадать пользователя. Такие случаи считаются отдельно, а эффект оценивается статистически (например, через event study или анализ baseline).*

## Демо-сценарий
MVP готов, когда вся цепочка работает на одном тестовом пользователе:
1. Создаем `placement` в Ad Registry.
2. Получаем уникальную ссылку и переходим в бота.
3. Бот создает `touch` и `lead`.
4. Добавляем тестовую оплату.
5. Система связывает события и показывает `attribution` и `ROMI`.

> **Offline Demo Mode:** Переход, лид и оплату можно симулировать без Telegram и интернета.

## Attribution vs Incrementality
Мы разделяем два понятия:
*   **Attribution** — распределение уже случившейся выручки (куда пошли деньги).
*   **Incrementality** — причинный эффект (сколько выручки не произошло бы без рекламы).

Для MVP используется детерминированная атрибуция. Продвинутые ML-модели и прогнозы продаж отложены как «future work», так как текущих данных недостаточно для их качественного обучения.

## Ответ на бизнес-вопрос
Вместо того чтобы гадать, какой канал лучше на основе прошлых данных, мы делаем следующий запуск **измеряемым экспериментом**. 
Каждое размещение получает `placement_id`, `cost` и `tracking link`. После запуска мы считаем `ROMI` и перераспределяем бюджет в пользу каналов с лучшим incremental contribution per ₽.

**Стек:** Python, Telegram Bot API, PostgreSQL, Pandas, Next.js, Vercel, Neon.

## Веб-версия и резервный Docker-контур

Production dashboard находится в `web/` и разворачивается на Vercel с Neon
Postgres. Route Handlers принимают кампании, placements, импорт продаж,
симуляцию событий и Telegram webhook. Корневой Python-контур остаётся
воспроизводимым fallback для локального запуска и VPS: Streamlit, PostgreSQL,
Excel-loader и long-polling bot используют одну базу.

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN, BOT_USERNAME и USER_HASH_SECRET
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app bot
```

`POSTGRES_PORT` — опубликованный host-порт; внутри Compose приложение всегда
подключается к `db:5432`. Volume `postgres_data` переживает перезапуск и
пересоздание контейнеров. Для исторического Excel:

```bash
mkdir -p data
cp /path/to/base.xlsx data/base.xlsx
docker compose --profile tools run --rm loader python scripts/load_sales.py
```

Переменные окружения:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`;
- `TELEGRAM_BOT_TOKEN`, `BOT_USERNAME`, `USER_HASH_SECRET`;
- `SOURCE_TIMEZONE`, `APP_PORT` и опциональный `STRIPE_SECRET_KEY`.

Без `USER_HASH_SECRET` bot завершается с понятной ошибкой. Сырые Telegram ID
не сохраняются: в БД попадает только HMAC user key. `/start <token>` создаёт
deterministic touch, `/start` без placement — organic/unknown touch. Обе CTA
создают один открытый lead на пару пользователь/курс даже при повторном нажатии;
уведомление менеджеру не имитируется до подключения CRM.

## Данные, attribution и ROMI

Каждая запись явно помечена происхождением: `real`, `synthetic`, `demo` в web
контуре и `observed`, `reconstructed`, `synthetic` в нормализованной PostgreSQL
схеме. Исторические строки `base.xlsx` реконструируются в candidate orders,
остаются без рекламного touch и поэтому не приписываются placement.

Last-touch выбирает последнее рекламное касание в окне 30 дней до оплаты;
касание после оплаты, старше окна или без placement игнорируется. Unknown revenue
показывается отдельно и не увеличивает ROMI placement. `ROMI_attr` —
revenue-based метрика `(attributed revenue - cost) / cost`; при нулевой стоимости
возвращается `N/A`. Это не incremental ROMI: causal-оценка требует holdout/A-B.

SQL-слой содержит отдельные витрины для attribution и `ROMI_inc`; демонстрационная
holdout-оценка всегда помечена `synthetic` и не является историческим доказательством.
Запуск демонстрационного отчёта:

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < sql/demo/002_demo_report.sql
```

## Vercel

Для `web/` задайте `DATABASE_URL`, `APP_PASSWORD`, `SESSION_SECRET`,
`USER_HASH_SECRET`, `BOT_USERNAME`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_WEBHOOK_SECRET` и `APP_URL`, затем
выполните миграцию и зарегистрируйте webhook:

```bash
cd web
npm ci
npm run db:migrate
npm run telegram:webhook
npm run build
```

Vercel-hosted webhook заменяет long polling и пишет в тот же measurement flow.
Incrementality и attribution — разные вопросы: первая требует эксперимента,
вторая объясняет, какой наблюдаемый доход можно связать с touch.
