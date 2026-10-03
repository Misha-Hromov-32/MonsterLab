#!/bin/sh
# Выкатка новой версии: забирает main, собирает образы и перезапускает сервис.
# Запуск на сервере: /root/MonsterLab/deploy/deploy.sh   (лог — в /root/monstorelab-deploy.log)
# Сторож на время выкатки отключается файлом .deploying.
set -eu
DIR=${DIR:-/root/MonsterLab}
cd "$DIR"
touch .deploying
trap 'rm -f "$DIR/.deploying"' EXIT

git pull --ff-only
docker compose build
docker compose up -d
# старые образы проекта после пересборки остаются «безымянными» и по 3 ГБ занимают диск
docker image prune -f --filter label=com.docker.compose.project=monster-lab >/dev/null
docker compose ps
