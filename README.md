<div align="center">

<img src="docs/images/banner.png" alt="Monster Lab — куда посмотрит покупатель до того, как карточка выйдет в выдачу" width="100%">

**Предиктивный тест обложек для Wildberries и Ozon:** куда упадёт взгляд покупателя, что потеряется
в маленькой карточке в ленте и какой вариант заметнее среди конкурентов.

**Попробовать без установки: [monsterlab.hromovms.ru](https://monsterlab.hromovms.ru/)**

<a href="https://monsterlab.hromovms.ru/"><img src="https://img.shields.io/badge/%D0%9F%D0%BE%D0%BF%D1%80%D0%BE%D0%B1%D0%BE%D0%B2%D0%B0%D1%82%D1%8C_%D0%BE%D0%BD%D0%BB%D0%B0%D0%B9%D0%BD-a366ff?style=for-the-badge" alt="Попробовать онлайн"></a>
<a href="#-быстрый-старт"><img src="https://img.shields.io/badge/%D0%91%D1%8B%D1%81%D1%82%D1%80%D1%8B%D0%B9_%D1%81%D1%82%D0%B0%D1%80%D1%82-1c1c1c?style=for-the-badge" alt="Быстрый старт"></a>
<a href="docs/architecture.md"><img src="https://img.shields.io/badge/%D0%9A%D0%B0%D0%BA_%D1%8D%D1%82%D0%BE_%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%D0%B5%D1%82-c095f9?style=for-the-badge" alt="Как это работает"></a>
<a href="docs/deploy.md"><img src="https://img.shields.io/badge/%D0%94%D0%B5%D0%BF%D0%BB%D0%BE%D0%B9_%D0%BD%D0%B0_%D1%81%D0%B5%D1%80%D0%B2%D0%B5%D1%80-dbf570?style=for-the-badge" alt="Деплой на сервер"></a>

[![CI](https://github.com/Misha-Hromov-32/MonsterLab/actions/workflows/ci.yml/badge.svg)](https://github.com/Misha-Hromov-32/MonsterLab/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-1c1c1c)

</div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/landing-dark.jpg">
  <img src="docs/images/landing.jpg" alt="Главная страница Monster Lab">
</picture>

## ✨ Что умеет

- 🔥 **Карта внимания** — нейросеть, обученная на записях реального движения глаз, показывает, куда посмотрят в первые секунды: тепло, туман, изолинии и порядок взгляда.
- 📏 **Понятные метрики** — «половина внимания на 9% площади», сколько элементов спорят за взгляд, прочитается ли текст в карточке шириной 170 px — и что исправить.
- 🛒 **Тест полки** — вариант ставится в выдачу рядом с конкурентами: заметят его или он сольётся.
- 🧑‍⚖️ **Экспертный разбор** — мультимодальные модели разбирают обложку как арт-директор и решают, на какой вариант скорее нажмут.
- 🪄 **Улучшенная обложка** — нейросеть перерисует обложку по выводам разбора: крупнее оффер, чище композиция, тот же товар.
- 🔎 **Конкуренты с Wildberries** — введите запрос, и тест полки возьмёт топ реальной выдачи.
- 🎯 **Вероятность выбора** — какой вариант скорее выберет покупатель, в процентах.
- 💳 **Подписка** — бесплатный тариф с лимитами и платный через ЮKassa.
- 🛠 **Админ-панель** — дизайн и тексты главной, свои примеры, ключ для экспертного разбора, цена и лимиты подписки.

<table>
<tr>
<td width="50%"><img src="docs/images/analyze.jpg" alt="Разбор обложки: тепловая карта и метрики"></td>
<td width="50%"><img src="docs/images/compare.jpg" alt="Сравнение вариантов с порядком взгляда"></td>
</tr>
</table>

## 🚀 Быстрый старт

Нужен [Docker](https://docs.docker.com/get-docker/) с Compose 2.24+.

```bash
git clone https://github.com/Misha-Hromov-32/MonsterLab.git && cd MonsterLab
cp .env.example .env          # задайте ADMIN_PASSWORD
docker compose up -d --build
```

Откройте **http://localhost:8080** и нажмите «Открыть пример». Первая сборка — 5–15 минут: скачиваются
PyTorch и веса нейросети. На слабом сервере поставьте `NEURAL=0` — соберётся лёгкий образ без нейросети.

Админ-панель — **http://localhost:8080/admin**. Экспертный разбор включается ключом [ProxyAPI](https://proxyapi.ru)
в админке, без ключа работает всё остальное.

## 📚 Документация

| | |
|---|---|
| [Как это работает](docs/architecture.md) | карта внимания, метрики и индекс, тест полки, устройство кода |
| [Деплой на сервер](docs/deploy.md) | Linux-сервер, HTTPS через Caddy, требования к памяти |
| [Настройки](docs/configuration.md) | все переменные окружения |
| [Участие в разработке](.github/CONTRIBUTING.md) | запуск без Docker, тесты, правила |

> [!IMPORTANT]
> Индекс заметности — инструмент для **сравнения вариантов одного товара между собой**, а не прогноз CTR:
> клики зависят ещё от цены, рейтинга и отзывов.

## 🙏 Благодарности

Карта внимания — [DeepGaze IIE](https://github.com/matthias-k/DeepGaze) (Linardos, Kümmerer, Press, Bethge,
[ICCV 2021](https://arxiv.org/abs/2105.12441)). Фото для примеров — [Unsplash](https://unsplash.com/license),
иконки — [Lucide](https://lucide.dev), шрифт — [Onest](https://fonts.google.com/specimen/Onest).

Код — [MIT](LICENSE).
