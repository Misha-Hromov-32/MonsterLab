#!/bin/sh
# Ежедневный бэкап MonStoreLab: базы SQLite (снимок без остановки сервиса), примеры, настройки и .env.
# Копия проверяется — база открывается, целостность ok, пользователи на месте. Старые копии удаляются.
# Если в .env задан BACKUP_REMOTE=user@host — копия без .env уходит на второй сервер (ключ
# /root/.ssh/monstorelab_backup, на втором сервере — rrsync «только запись», см. docs/deploy.md).
# Итог пишется в backup-status.json тома data — его показывает отчёт в ВК (services/report.py).
# Запуск: /root/MonsterLab/deploy/backup.sh   (по расписанию — deploy/monstorelab-backup.timer)
set -eu
DIR=${DIR:-/root/MonsterLab}
DEST=${DEST:-/root/backups}
KEEP_DAYS=${KEEP_DAYS:-14}
KEY=/root/.ssh/monstorelab_backup
VOL=/var/lib/docker/volumes/monster-lab_data/_data
C=monster-lab-backend-1
NAME=monsterlab-auto-$(date +%Y%m%d-%H%M)
B=$DEST/$NAME
REMOTE=$(grep -E '^BACKUP_REMOTE=' "$DIR/.env" 2>/dev/null | cut -d= -f2- | tr -d '"\r' || true)
umask 077

status() {  # ok, users, size_mb, remote, error
  printf '{"at": %s, "ok": %s, "name": "%s", "users": %s, "size_mb": %s, "remote": "%s", "error": "%s"}\n' \
    "$(date +%s)" "$1" "$NAME" "$2" "$3" "$4" "$5" > "$VOL/backup-status.json.tmp"
  chmod 644 "$VOL/backup-status.json.tmp" && mv "$VOL/backup-status.json.tmp" "$VOL/backup-status.json"
}
fail() {
  echo "Бэкап не удался: $1" >&2
  logger -t monstorelab-backup "Бэкап не удался: $1"
  status false 0 0 none "$1"
  exit 1
}

mkdir -p "$B"
# снимок через sqlite3.backup — согласованная копия, даже если в этот момент идёт запись
docker exec "$C" python -c "
import sqlite3
for n in ('app', 'examples'):
    s = sqlite3.connect(f'/data/{n}.sqlite'); d = sqlite3.connect(f'/tmp/{n}.bak.sqlite')
    s.backup(d); d.close(); s.close()
" || fail "снимок базы в контейнере"
docker cp -q "$C:/tmp/app.bak.sqlite" "$B/app.sqlite" || fail "копирование app.sqlite"
docker cp -q "$C:/tmp/examples.bak.sqlite" "$B/examples.sqlite" || fail "копирование examples.sqlite"
docker exec "$C" rm -f /tmp/app.bak.sqlite /tmp/examples.bak.sqlite || true
tar czf "$B/files.tgz" -C "$VOL" settings.json examples competitors || fail "архив примеров и настроек"
cp "$DIR/.env" "$B/env" || fail "копия .env"

USERS=$(python3 - "$B/app.sqlite" <<'EOF'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
assert c.execute("pragma integrity_check").fetchone()[0] == "ok"
print(c.execute("select count(*) from users").fetchone()[0])
EOF
) || fail "проверка копии: база не открывается или повреждена"
[ "$USERS" -gt 0 ] || fail "в копии нет пользователей"
gzip -9 "$B/app.sqlite" "$B/examples.sqlite" || fail "сжатие баз"
SIZE=$(du -sm "$B" | cut -f1)

RSTATE=off
if [ -n "$REMOTE" ]; then
  if rsync -a --exclude env -e "ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new" \
    "$B/" "$REMOTE:$NAME/"; then
    RSTATE=ok
  else
    RSTATE=failed
    logger -t monstorelab-backup "Копия на второй сервер ($REMOTE) не ушла"
  fi
fi

# старые автокопии — прочь; ручные (monsterlab-ГГГГММДД-…) не трогаем
find "$DEST" -mindepth 1 -maxdepth 1 -type d -name 'monsterlab-auto-*' -mtime +"$KEEP_DAYS" -exec rm -rf {} +
status true "$USERS" "$SIZE" "$RSTATE" ""
logger -t monstorelab-backup "Бэкап $NAME: пользователей $USERS, $SIZE МБ, второй сервер: $RSTATE"
echo "Бэкап $NAME: пользователей $USERS, $SIZE МБ, второй сервер: $RSTATE"
