# Генератор обложек для встроенных примеров

Встроенные примеры (`backend/seed`) — обложки в стиле инфографики маркетплейсов: настоящие фотографии
товаров с Unsplash, вырезанные от фона и свёрстанные в HTML/CSS. Здесь — всё, чтобы пересобрать их
или добавить новый набор.

```
sets.json ──► prepare_products.py ──► cut/*.png ──► make_covers.py ──► out/*.png ──► backend/seed/
 (тексты,        (скачать фото,        (товар без      (вёрстка HTML,       (обложки     (--seed: 720×960
  цвета, id фото) вырезать фон)         фона)           снимок Chrome)       900×1200)    + manifest.json)
```

## Запуск

Нужны Python 3.11+, Node 20+ и Google Chrome (или Edge; путь можно задать переменной `CHROME`).

```bash
cd tools/covers
pip install -r requirements.txt     # Pillow, rembg (скачает модель вырезки ~170 МБ при первом запуске)
npm install                         # иконки Lucide для шаблонов

python prepare_products.py          # фото → stock/, товары без фона → cut/
python make_covers.py               # все наборы → out/
python make_covers.py coffee        # только один набор
python make_covers.py --seed        # + обновить backend/seed
```

Папки `stock/`, `cut/`, `html/`, `out/` — промежуточные, в git не попадают.

## sets.json

Ключ — `slug` набора (он же id встроенного примера). Внутри:

| Поле | Что это |
|---|---|
| `title`, `description`, `context` | название примера, подпись и данные о товаре (запрос, категория, цена) |
| `rev` | ревизия: увеличьте, выполните `make_covers.py --seed` и пересоберите образ — сервис обновит уже разложенный пример |
| `photos` | id фотографий Unsplash; `cut` в карточке (`thermos-0`) — какой вырезанный товар из `cut/` взять |
| `variants` | 4 варианта обложки: шаблон `t` (`infographic`, `scene`, `clean`, `offer`), тексты, цвета, бейджи |
| `competitors` | обложки «конкурентов» для теста полки — те же шаблоны с другими брендами и цветами |

Лицензия Unsplash разрешает бесплатное, в том числе коммерческое, использование; источники перечислены
в `backend/seed/CREDITS.md`.
