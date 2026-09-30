#!/bin/sh
# Запускает сервис от непривилегированного пользователя app.
# Том /data мог быть создан старой версией от root — сначала возвращаем его пользователю app.
set -e
if [ "$(id -u)" = "0" ]; then
  chown -R app:app /data
  # setpriv не меняет окружение: без своего HOME процесс видел бы /root, куда app не пишет,
  # и Chromium (подбор конкурентов) падал бы на старте — ему нужен каталог для служебных файлов
  HOME=/home/app exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
