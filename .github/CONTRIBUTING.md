# Как участвовать

Спасибо, что заглянули! Ниже — всё, что нужно, чтобы поднять проект локально и прислать изменение.

## Окружение

| Что | Версия |
|---|---|
| Python | 3.11+ (в Docker — 3.12) |
| Node.js | 20.19+ или 22.12+ (в Docker — 22) |
| Docker | с Compose 2.24+ — для полного запуска |

## Бэкенд

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows, Git Bash: source .venv/Scripts/activate
pip install -r requirements-dev.txt
ENGINE=classic uvicorn app.main:app --reload
```

В PowerShell:

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:ENGINE = "classic"; uvicorn app.main:app --reload
```

`ENGINE=classic` запускает сервис без нейросети — для разработки этого хватает, и не нужно ставить
PyTorch. С нейросетью (в том же окружении):

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1
pip install -r requirements-neural.txt
```

Проверки:

```bash
ruff check . ../tools    # правила — в backend/pyproject.toml
ruff format --check . ../tools
pytest
```

## Фронтенд

```bash
cd frontend
npm ci
npm run dev             # http://localhost:5173, /api проксируется на :8000
```

Если бэкенд запущен в Docker, укажите его адрес: `API_URL=http://127.0.0.1:8080 npm run dev`.

Перед коммитом:

```bash
npm run format          # prettier
npm test                # vitest: юнит-тесты src/**/*.test.ts
npm run build           # vue-tsc + vite build
```

## Правила

- **Интерфейс — для селлера, не для инженера.** Никаких CPU, SSIM, названий нейросетей и формул в UI:
  только понятные слова и выводы, с которыми можно что-то сделать.
- **Комментарии — по-русски**, коротко и о том, *почему*, а не *что*.
- **Коммиты** — в стиле [Conventional Commits](https://www.conventionalcommits.org/ru/): `feat:`, `fix:`,
  `refactor:`, `docs:`, `chore:`. Описание — по-русски.
- **Новые метрики** — с понятным смыслом и порогами в именованных константах (`backend/app/core/metrics.py`),
  плюс тест.
- Лимиты (4 варианта, 12 конкурентов, 6 моделей) заданы и на сервере (`backend/app/config.py`),
  и в интерфейсе (`frontend/src/lib/constants.ts`) — меняйте в обоих местах.

## Встроенные примеры

Обложки для примеров собираются из фотографий Unsplash — см. [tools/covers/README.md](../tools/covers/README.md).
После изменения увеличьте `rev` набора в `tools/covers/sets.json`, выполните
`python make_covers.py --seed` и пересоберите образ: сервис заменит картинки у уже разложенного примера.
