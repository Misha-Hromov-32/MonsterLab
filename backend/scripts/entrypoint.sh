#!/bin/sh
# Запускает сервис от непривилегированного пользователя app.
# Том /data мог быть создан старой версией от root — сначала возвращаем его пользователю app.
set -e
if [ "$(id -u)" = "0" ]; then
  chown -R app:app /data
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
