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
| `VISUAL_MODEL` | `anthropic/claude-sonnet-5-5` | модель визуального разбора; если не ответит — первая из `EXPERT_MODELS` |
| `NEURAL` | `1` | `0` — образ без нейросети |
| `ENGINE` | `auto` | `classic` — не загружать нейросеть, даже если она есть |
| `DEEPGAZE_SIDE` | `768` | размер картинки для нейросети: больше — точнее и медленнее |
| `TORCH_THREADS` | `0` (авто) | потоков для нейросети |
| `QUEUE_NEURAL_WORKERS` | `2` | одновременных задач нейросети внимания (анализ, тест полки) |
| `QUEUE_AI_WORKERS` | `4` | одновременных визуальных разборов и выборов покупателя |
| `QUEUE_IMAGE_WORKERS` | `2` | одновременных генераций улучшенной обложки |
| `QUEUE_BROWSER_WORKERS` | `1` | одновременных подборов конкурентов (Chromium) |
| `QUEUE_PER_USER` | `8` | задач одного покупателя в работе и в ожидании |
| `QUEUE_MAX_WAITING` | `300` | ожидающих в одной полосе — дальше «сервис перегружен» |
| `QUEUE_MAX_WAIT_S` | `900` | сколько задача может простоять в очереди |
| `QUEUE_JOB_TIMEOUT_S` | `600` | сколько может выполняться одна задача |
| `MAX_UPLOAD_MB` | `25` | максимальный размер одного файла; подняли — поднимите и `client_max_body_size` в `frontend/nginx.conf.template` |
| `DATA_DIR` | `/data` в Docker, `backend/data` локально | где хранить настройки, примеры и личные обложки пользователей (`app.sqlite`) |
| `STATIC_DIR` | — | путь к собранному фронтенду: бэкенд отдаст его сам, без nginx |
| `TRUST_PROXY` | `1` в `docker-compose.yml` | верить `X-Real-IP` от nginx при подсчёте лимитов |
| `REAL_IP_FROM` | `127.0.0.1` (никому) | адреса внешнего HTTPS-прокси, которому nginx верит в `X-Forwarded-For` |
| `IMAGE_MODEL` | `openai/gpt-image-2` | модель ProxyAPI для улучшенной обложки (эндпоинт `/images/edits`) |
| `IMAGE_QUALITY` | `medium` | качество генерации: `medium` или `high` (в 3–4 раза дороже и дольше) |
| `MARKETPLACE` | `1` | `0` — образ без браузера: подбор конкурентов с Wildberries выключен |
| `BROWSER_PATH` | — | путь к своему Chrome/Chromium для подбора конкурентов при запуске без Docker |
| `COMPETITORS_CACHE_HOURS` | `24` | сколько часов хранить найденную выдачу по одному запросу |
| `PAYMENT_PROVIDER` | `tochka`, если задан `TOCHKA_JWT`, иначе `yookassa` | через кого принимать оплату |
| `TOCHKA_JWT` | — | JWT-ключ из интернет-банка Точки с правами на интернет-эквайринг |
| `TOCHKA_CLIENT_ID` | — | client_id приложения Точки — для регистрации вебхука |
| `TOCHKA_CUSTOMER_CODE` | — | код бизнес-клиента (`GET /open-banking/v1.0/customers`, `customerType: Business`) |
| `TOCHKA_MERCHANT_ID` | — | торговая точка, 15 цифр (`GET /acquiring/v1.0/retailers`) — нужна, если точек несколько |
| `TOCHKA_RECEIPT` | `1` | чек по 54-ФЗ через кассу Точки (email покупателя, услуга без НДС) |
| `TOCHKA_TAX_SYSTEM` | — | система налогообложения в чеке: `osn`, `usn_income`, `usn_income_outcome`, `esn`, `patent`; пусто — как в кассе |
| `YOOKASSA_SHOP_ID` | — | shopId магазина в ЮKassa; без него и ключа оплата выключена |
| `YOOKASSA_SECRET_KEY` | — | секретный ключ ЮKassa |
| `YOOKASSA_RECEIPT` | `0` | `1` — передавать чек по 54-ФЗ через ЮKassa (email покупателя, услуга) |
| `YOOKASSA_VAT_CODE` | `1` | код НДС в чеке: 1 — без НДС (см. документацию ЮKassa) |
| `PUBLIC_URL` | `http://localhost:8080` | адрес сайта: из него собираются ссылки в письмах, сюда ЮKassa вернёт покупателя после оплаты |
| `MASTER_KEY` | генерируется в `DATA_DIR/.master_key` | мастер-ключ шифрования, 64 hex-символа (`openssl rand -hex 32`); из него выводятся ключи для email, паролей и токенов |
| `SMTP_HOST` | — | почтовый сервер; без него письма не уходят, а пишутся в журнал бэкенда |
| `SMTP_PORT` | `465` | порт почтового сервера |
| `SMTP_SECURITY` | `ssl` для 465, иначе `starttls` | `ssl`, `starttls` или `none` (только для отладки) |
| `SMTP_USER` | — | логин почтового ящика |
| `SMTP_PASSWORD` | — | пароль (для Яндекса и Mail.ru — пароль приложения) |
| `MAIL_FROM` | `SMTP_USER` | адрес отправителя |
| `MAIL_FROM_NAME` | `MonStoreLab` | имя отправителя |
| `MAIL_REPLY_TO` | — | куда приходят ответы на письма сервиса (Reply-To), если отправитель — noreply@… |
| `VK_CLIENT_ID` | — | ID приложения VK ID (id.vk.ru, платформа «Веб»; Redirect URL — `PUBLIC_URL/auth/vk/callback`, доступ `email`) — включает кнопку «Войти с VK ID» |
| `YANDEX_CLIENT_ID` | — | ClientID приложения на oauth.yandex.ru (Redirect URI — `PUBLIC_URL/auth/yandex/callback`, доступ к почте) |
| `YANDEX_CLIENT_SECRET` | — | секрет приложения Яндекс ID; без него кнопка Яндекса не показывается |
| `LEGAL_OPERATOR` | — | оператор персональных данных для страницы `/legal`: «ИП Иванов Иван Иванович, ИНН …, ОГРНИП …, адрес …» |
| `LEGAL_EMAIL` | `MAIL_FROM` | адрес для обращений по данным: отзыв согласия, удаление аккаунта |

Изменили `.env` — перезапустите: `docker compose up -d`. `NEURAL` и `MARKETPLACE` влияют на сборку образа,
поэтому после них нужна пересборка: `docker compose up -d --build`.

`MASTER_KEY` задайте до первой регистрации и храните копию отдельно от сервера: сменить его нельзя —
зашифрованные email станут нечитаемыми. Если не задан, ключ создаётся в томе `data` (`/data/.master_key`)
рядом с базой: всё работает, но копия тома тогда раскрывает и ключ. На боевом сервере задайте `MASTER_KEY`
в `.env`.

Почта: подойдёт любой SMTP — Яндекс 360 (`smtp.yandex.ru`, 465), Mail.ru (`smtp.mail.ru`, 465),
Unisender Go, SendPulse и т. п. Чтобы письма не попадали в спам, настройте у домена отправителя SPF и DKIM.

Тарифы (название, цена, срок), демо-квоты и квоты тарифов настраиваются в админ-панели («Тарифы»).
В ЮKassa в разделе «HTTP-уведомления» укажите адрес `https://ваш-домен/api/billing/webhook`
и событие `payment.succeeded`.

### Точка Банк: вебхук об оплате

Уведомления об оплате (`acquiringInternetPayment`) регистрируются один раз на client_id приложения:

```bash
curl -X PUT "https://enter.tochka.com/uapi/webhook/v1.0/$TOCHKA_CLIENT_ID"   -H "Authorization: Bearer $TOCHKA_JWT" -H "Content-Type: application/json"   -d '{"webhooksList": ["acquiringInternetPayment"], "url": "https://ваш-домен/api/billing/webhook"}'
```

API Точки подписан сертификатом Минцифры (Russian Trusted Root CA) — он лежит в
`backend/app/certs/russian_trusted_ca.pem`; для `curl` с сервера добавьте `--cacert` с этим файлом.
Уведомлению сервис не верит: платёж всегда перепроверяется запросом к Точке, а после возврата со страницы
оплаты сайт сам просит сервер проверить платёж (`POST /api/billing/check`).
