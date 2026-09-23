# Monster Lab на Linux-сервере

Проверено на сервере с 2 CPU, 4 ГБ RAM и 30 ГБ диска: нейросеть занимает 1,1–1,3 ГБ памяти,
анализ обложки — 2–5 с, тест полки — 10–20 с.

| Сервер | Что ставить |
|---|---|
| от 2 ГБ RAM | полный образ (по умолчанию) |
| 1 ГБ RAM и меньше | `NEURAL=0` в `.env` — без нейросети, ~70 МБ памяти, анализ за доли секунды |

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
nano .env        # впишите ADMIN_PASSWORD=свой_пароль (остальное можно не трогать)
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

Обновить: `git pull` (или скопировать новые файлы поверх, кроме `.env`) и снова `docker compose up -d --build`.
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
