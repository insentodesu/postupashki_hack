#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

say() { printf '\n%s\n' "$1"; }
fail() { printf '\nОшибка: %s\n' "$1" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker не найден. Установите Docker Desktop или Docker Engine и повторите запуск."
docker compose version >/dev/null 2>&1 || fail "Нужен Docker Compose v2. Запускайте команду из Docker Desktop или современного Docker Engine."
command -v curl >/dev/null 2>&1 || fail "curl не найден. Он нужен для проверки готовности панели."

if [[ ! -f .env ]]; then
  cp .env.example .env
  say "Создан .env из шаблона. Заполните секреты и запустите ./deploy.sh ещё раз."
  printf '%s\n' "Обязательные поля: TELEGRAM_BOT_TOKEN, BOT_USERNAME, USER_HASH_SECRET, POSTGRES_PASSWORD."
  exit 0
fi

set -a
# .env создаёт оператор; файл намеренно не попадает в Git.
# shellcheck disable=SC1091
source .env
set +a

[[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] || fail "В .env не задан TELEGRAM_BOT_TOKEN."
[[ -n "${BOT_USERNAME:-}" ]] || fail "В .env не задан BOT_USERNAME."
[[ -n "${USER_HASH_SECRET:-}" ]] || fail "В .env не задан USER_HASH_SECRET."
[[ "${USER_HASH_SECRET}" != "change_me" ]] || fail "Замените USER_HASH_SECRET на случайную строку."
[[ ${#USER_HASH_SECRET} -ge 24 ]] || fail "USER_HASH_SECRET должен быть длиной не менее 24 символов."
[[ -n "${POSTGRES_PASSWORD:-}" ]] || fail "В .env не задан POSTGRES_PASSWORD."
[[ "${POSTGRES_PASSWORD}" != "change_me" ]] || fail "Замените POSTGRES_PASSWORD на пароль базы."

APP_PORT="${APP_PORT:-8501}"
say "Собираем образ и запускаем dashboard, bot и PostgreSQL..."
docker compose up -d --build

say "Ждём готовность панели..."
ready=0
for _ in {1..36}; do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/_stcore/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "$ready" -ne 1 ]]; then
  docker compose ps
  docker compose logs --tail=80 app db
  fail "Панель не ответила за 72 секунды. Смотрите логи выше."
fi

docker compose ps
say "Готово"
printf '%s\n' "Панель: http://localhost:${APP_PORT}"
printf '%s\n' "Логи:   docker compose logs -f app bot"
printf '%s\n' "Стоп:   docker compose down"
printf '%s\n' "Бэкап:  docker compose exec -T db pg_dump -U \"$POSTGRES_USER\" \"$POSTGRES_DB\" > backup-$(date +%Y%m%d-%H%M).sql"
