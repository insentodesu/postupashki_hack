# Запуск проекта одной командой

Это короткий путь для сервера или локального компьютера. Проект запускается через Docker Compose: база, панель и Telegram-бот стартуют из одного репозитория. Так надёжнее, чем держать три постоянно работающих процесса в одном контейнере.

## Что нужно заранее

1. Установить Docker Desktop (macOS/Windows) или Docker Engine (Linux).
2. Скопировать репозиторий на машину.
3. Получить токен Telegram-бота и придумать два секрета.

## Первый запуск

В папке проекта выполните:

```bash
chmod +x deploy.sh
./deploy.sh
```

При первом запуске скрипт создаст `.env` и остановится, чтобы вы заполнили секреты. Откройте `.env` и задайте:

```dotenv
TELEGRAM_BOT_TOKEN=токен_от_BotFather
BOT_USERNAME=имя_бота_без_символа_@
USER_HASH_SECRET=длинная_случайная_строка_не_короче_24_символов
POSTGRES_PASSWORD=отдельный_пароль_базы
```

После этого повторите `./deploy.sh`. Через минуту панель будет доступна по адресу `http://localhost:8501`. На VPS замените `localhost` на IP сервера и откройте входящий TCP-порт 8501 в firewall.

PostgreSQL наружу не публикуется. К базе могут подключаться только контейнеры этого проекта. Для просмотра данных используйте `docker compose exec db psql`.

## Проверка после запуска

Откройте панель, создайте campaign и placement, скопируйте deep link, перейдите по нему в Telegram, создайте lead и добавьте тестовую оплату. В сводке должны появиться touch, lead, revenue и deterministic attribution. Оплата без tracking link должна остаться в unknown revenue.

Загрузить исторический Excel можно из раздела «Операции». Для ручного запуска loader из файла `data/base.xlsx`:

```bash
mkdir -p data
cp /путь/к/base.xlsx data/base.xlsx
docker compose --profile tools run --rm loader python scripts/load_sales.py
```

## Повседневные команды

```bash
docker compose ps                         # состояние сервисов
docker compose logs -f app bot            # логи панели и бота
docker compose restart                     # быстрый перезапуск
docker compose up -d --build               # обновить код и пересобрать образ
docker compose down                        # остановить, не удаляя базу
```

Данные лежат в именованном Docker volume `postgres_data`, поэтому обычный `down` и перезапуск их не удаляют. Перед обновлением можно сделать SQL-бэкап:

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup-$(date +%Y%m%d-%H%M).sql
```

Не коммитьте `.env`, бэкапы и токен Telegram. Если бот не стартует, первым делом проверьте `TELEGRAM_BOT_TOKEN`, `BOT_USERNAME` и `USER_HASH_SECRET` в `.env`.

## Обновление на VPS

```bash
git pull
./deploy.sh
```

Скрипт сам пересоберёт образ, поднимет сервисы и дождётся ответа панели. Если healthcheck не проходит, он покажет последние логи `app` и `db`.

## Что разворачивается

- `db`: PostgreSQL 16 с постоянным volume;
- `app`: резервная Streamlit-панель на порту 8501;
- `bot`: long polling Telegram-бот, работающий с той же базой;
- `loader`: одноразовый профиль для загрузки Excel.

Веб-версия в папке `web/` по-прежнему разворачивается отдельно на Vercel с Neon. Этот Docker-запуск нужен как полностью автономный контур для локальной машины или VPS.
