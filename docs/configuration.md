# Настройки

Все переменные необязательны. Задаются в `.env` рядом с `docker-compose.yml` — шаблон с комментариями
в [.env.example](../.env.example).

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `ADMIN_PASSWORD` | генерируется | пароль админ-панели |
| `PORT` | `8080` | порт интерфейса на хосте |
| `PROXYAPI_KEY` | — | ключ экспертного разбора, если не задан в админке |
| `PROXYAPI_BASE_URL` | `https://api.proxyapi.ru/v1` | OpenAI-совместимый адрес |
| `EXPERT_MODELS` | `google/gemini-2.5-flash,anthropic/claude-haiku-4-5` | модели через запятую, до 6 |
| `EXPERT_CONCURRENCY` | `6` | одновременных запросов к моделям |
| `NEURAL` | `1` | `0` — образ без нейросети |
| `ENGINE` | `auto` | `classic` — не загружать нейросеть, даже если она есть |
| `DEEPGAZE_SIDE` | `768` | размер картинки для нейросети: больше — точнее и медленнее |
| `TORCH_THREADS` | `0` (авто) | потоков для нейросети |
| `BACKEND_MEM_LIMIT` | `1800m` | потолок памяти контейнера бэкенда |
| `MAX_UPLOAD_MB` | `25` | максимальный размер одного файла |
| `DATA_DIR` | `/data` в Docker, `backend/data` локально | где хранить настройки и примеры |
| `STATIC_DIR` | — | путь к собранному фронтенду: бэкенд отдаст его сам, без nginx |
| `TRUST_PROXY` | `1` в `docker-compose.yml` | верить `X-Real-IP` от nginx при подсчёте лимитов |
| `REAL_IP_FROM` | `127.0.0.1` (никому) | адреса внешнего HTTPS-прокси, которому nginx верит в `X-Forwarded-For` |

Изменили `.env` — перезапустите: `docker compose up -d`. `NEURAL` влияет на сборку образа, поэтому после
него нужна пересборка: `docker compose up -d --build`.
