#!/bin/sh
# Сторож MonStoreLab: раз в минуту (systemd-таймер monstorelab-watchdog.timer) проверяет /api/health
# через nginx контейнера. Три неудачи подряд — поднимает и перезапускает контейнеры.
# Docker сам перезапускает упавший контейнер (restart: unless-stopped), но не «зависший» —
# для этого и нужен сторож. Во время выкатки (файл .deploying) проверка пропускается.
set -u
DIR=${DIR:-/root/MonsterLab}
STATE=/run/monstorelab-watchdog.fails
LIMIT=3

[ -e "$DIR/.deploying" ] && exit 0
# адрес из PORT в .env: «127.0.0.1:8092» или просто «8092»
port=$(sed -n 's/^PORT=//p' "$DIR/.env" 2>/dev/null | tail -1)
port=${port:-8080}
case "$port" in *:*) url="http://$port/api/health" ;; *) url="http://127.0.0.1:$port/api/health" ;; esac

if curl -fsS -m 20 "$url" >/dev/null 2>&1; then
  echo 0 >"$STATE"
  exit 0
fi

fails=$(($(cat "$STATE" 2>/dev/null || echo 0) + 1))
echo "$fails" >"$STATE"
logger -t monstorelab-watchdog "сайт не отвечает: $url ($fails из $LIMIT)"
if [ "$fails" -ge "$LIMIT" ]; then
  logger -t monstorelab-watchdog "перезапускаю контейнеры"
  cd "$DIR" && docker compose up -d && docker compose restart
  echo 0 >"$STATE"
fi
