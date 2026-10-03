# MonStoreLab на Linux-сервере

Рекомендуемый сервер — 4 CPU, 8 ГБ RAM, 60 ГБ диска: нейросеть занимает 1,1–1,6 ГБ памяти, Chromium
для подбора конкурентов — ещё ~200 МБ на время поиска, образ бэкенда — ~3,2 ГБ. Анализ обложки — 2–5 с,
тест полки — 10–20 с.

Лимитов памяти и процессора у контейнеров нет: нагрузку держит очередь задач (`QUEUE_*` в `.env`,
см. [настройки](configuration.md)). Сколько бы покупателей ни нажали кнопку, одновременно выполняется
ограниченное число тяжёлых задач, остальные ждут и видят своё место в очереди.

| Сервер | Что ставить |
|---|---|
| от 4 ГБ RAM | полный образ (по умолчанию) |
| 1–2 ГБ RAM | `NEURAL=0` и `MARKETPLACE=0` в `.env` — без нейросети и браузера, ~70 МБ памяти |

Собирать образ с нейросетью рядом с работающим бэкендом на маленьком сервере нельзя: установка PyTorch
съедает ~1 ГБ памяти. На 4 ГБ и меньше — сначала `docker compose stop backend`, потом сборка.

## 1. Docker (один раз)

Ubuntu / Debian:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # затем перелогиньтесь
```

## 2. Загрузить проект

Из git:

```bash
cd /opt && git clone https://github.com/Misha-Hromov-32/MonsterLab.git monster-lab && cd monster-lab
```

или упакуйте проект на компьютере без лишнего (`node_modules`, `.venv`, `.git`) и перенесите архив
(подставьте свой IP):

```bash
git archive --format=tar.gz -o monster-lab.tgz HEAD
scp monster-lab.tgz root@IP_СЕРВЕРА:/opt/
ssh root@IP_СЕРВЕРА 'mkdir -p /opt/monster-lab && tar -xzf /opt/monster-lab.tgz -C /opt/monster-lab'
```

На сервере:

```bash
cd /opt/monster-lab
cp .env.example .env
nano .env        # впишите ADMIN_PASSWORD, MASTER_KEY, PUBLIC_URL и почту SMTP_* (см. docs/configuration.md)
```

## 3. Запустить

```bash
docker compose up -d --build
```

Первая сборка — 5–15 минут: скачиваются PyTorch и веса нейросети (~1,5 ГБ). Дальше перезапуск — секунды.

Сайт: `http://IP_СЕРВЕРА:8080`, админка: `http://IP_СЕРВЕРА:8080/admin`.

Сайт не открывается? Docker публикует порт в обход ufw — проверьте файрвол в панели хостера.
Закрыть прямой доступ к порту можно через `PORT=127.0.0.1:8080` (см. ниже).

## Полезное

```bash
docker compose ps                  # что запущено
docker compose logs -f backend     # журнал
docker compose restart             # перезапуск
docker compose down                # остановить (данные сохраняются)
```

Обновить: `git pull` и снова `docker compose up -d --build`. Каждая сборка оставляет старый образ без тега
(~3 ГБ) — после обновления удаляйте их, иначе диск закончится:

```bash
docker image prune -f --filter "label=com.docker.compose.project=monster-lab"
```
Настройки, примеры, ключ ProxyAPI и сгенерированный пароль хранятся в docker-томе `monster-lab_data`
и при обновлении не теряются. Забыли пароль — `docker compose exec backend cat /data/admin_password.txt`.

## Домен и HTTPS (по желанию)

Если есть домен, направьте его A-записью на IP сервера и поставьте Caddy — он сам получит сертификат:

```bash
sudo apt-get install -y caddy
echo 'cover.вашдомен.ru {
    reverse_proxy 127.0.0.1:8080
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Затем в `.env` закройте прямой доступ к порту и скажите nginx, что перед ним стоит свой прокси, —
иначе все посетители будут выглядеть для лимитов одним адресом:

```bash
PORT=127.0.0.1:8080
REAL_IP_FROM=172.16.0.0/12   # сеть Docker: оттуда приходят запросы от Caddy
```

и перезапустите: `docker compose up -d`. `REAL_IP_FROM` включайте только вместе с `PORT=127.0.0.1:…`:
если порт открыт наружу, адрес в `X-Forwarded-For` сможет подставить кто угодно.

## Автоперезапуск и выкатка обновлений

Docker сам поднимает контейнеры после перезагрузки сервера и после падения (`restart: unless-stopped`),
но не трогает «зависший» сервис. Для этого есть сторож — systemd-таймер, который раз в минуту проверяет
`/api/health` и после трёх неудач подряд перезапускает контейнеры (`deploy/watchdog.sh`):

```bash
cp /root/MonsterLab/deploy/monstorelab-watchdog.* /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now monstorelab-watchdog.timer
journalctl -t monstorelab-watchdog   # что и когда сторож перезапускал
```

Скрипт и юниты рассчитаны на проект в `/root/MonsterLab`; в другом месте поправьте путь в
`monstorelab-watchdog.service` и `DIR` в скриптах.

Новая версия выкатывается одной командой — она забирает `main`, собирает образы, перезапускает сервис
и удаляет старые образы (иначе каждая сборка оставляет ~3 ГБ на диске). Сторож на это время отключается:

```bash
/root/MonsterLab/deploy/deploy.sh
```
