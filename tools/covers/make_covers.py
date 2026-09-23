"""Шаг 2: верстает обложки в стиле маркетплейсной инфографики и (по флагу) кладёт их в сид бэкенда.

    python make_covers.py                  # все наборы → out/*.png
    python make_covers.py coffee cream     # только выбранные
    python make_covers.py --seed           # + пересобрать backend/seed целиком (нужны все наборы в out/)

Каждая обложка — HTML/CSS-страница 900×1200 (шрифт Montserrat, иконки Lucide), которую снимает
headless Chrome. Тексты, цвета и шаблон каждой карточки задаются в sets.json.
Перед запуском: `npm install` (иконки) и `python prepare_products.py` (вырезанные товары).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CUT = HERE / "cut"
ICONS = HERE / "node_modules" / "lucide-static" / "icons"
OUT = HERE / "out"
HTML = HERE / "html"
SEED = HERE.parent.parent / "backend" / "seed"

CREDITS = """\
# Источники изображений

Фото товаров — [Unsplash](https://unsplash.com), [лицензия Unsplash](https://unsplash.com/license):
бесплатно для любого, в том числе коммерческого, использования. id фото — в `tools/covers/sets.json` (поле `photos`).

Фон вырезан нейросетью rembg, обложки свёрстаны в HTML/CSS скриптом `tools/covers/make_covers.py`.
Бренды на конкурентах вымышленные либо взяты с упаковок на исходных фото.
"""

FONTS = (
    '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&display=block"'
    ' rel="stylesheet">'
)


def find_chrome() -> str:
    """Chrome, Chromium или Edge: переменная CHROME, затем типичные пути Windows / macOS / Linux."""
    candidates = [
        os.environ.get("CHROME", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    sys.exit("Не найден Chrome/Chromium. Укажите путь в переменной окружения CHROME.")


def icon(name, color="#fff", size=34):
    svg = (ICONS / f"{name}.svg").read_text()
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"').replace('stroke-width="2"', 'stroke-width="2.4"')
    return svg.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')


def img(cut):
    return (CUT / f"{cut}.png").as_uri()


BASE_CSS = """
*{box-sizing:border-box;margin:0}
body{width:900px;height:1200px;overflow:hidden;font-family:Montserrat,sans-serif}
.card{position:relative;width:900px;height:1200px;overflow:hidden}
.prod{position:absolute;display:flex;align-items:flex-end;justify-content:center}
.prod img{width:100%;height:100%;object-fit:contain;object-position:center bottom;filter:drop-shadow(0 38px 36px rgba(0,0,0,.35)) drop-shadow(0 6px 10px rgba(0,0,0,.18))}
h1{font-weight:900;text-transform:uppercase;letter-spacing:-.02em;line-height:.9}
.ben{display:flex;align-items:center;gap:16px;padding:12px 22px 12px 12px;border-radius:24px;font-weight:700;font-size:28px;line-height:1.1}
.ic{flex:none;display:grid;place-items:center;width:60px;height:60px;border-radius:50%}
.round{position:absolute;display:grid;place-items:center;align-content:center;border-radius:50%;text-align:center;font-weight:900}
.round b{display:block;font-size:64px;line-height:.9;letter-spacing:-.03em}
.round small{display:block;font-size:22px;font-weight:700;text-transform:uppercase;margin-top:4px}
.sticker{position:absolute;padding:14px 26px;border-radius:16px;font-weight:900;font-size:34px;text-transform:uppercase;letter-spacing:.01em}
.brand{position:absolute;font-weight:800;font-size:26px;letter-spacing:.14em;text-transform:uppercase}
"""


def page(body, css):
    return f"<!doctype html><html><head><meta charset='utf-8'>{FONTS}<style>{BASE_CSS}{css}</style></head><body>{body}</body></html>"


# ------------------------------------------------------------ шаблоны


def t_infographic(d):
    """Яркий градиент, огромный заголовок, 3 преимущества слева, товар справа, круглый бейдж и стикер."""
    c1, c2, acc = d["colors"]
    bens = "".join(
        f'<div class="ben"><span class="ic" style="background:{acc}">{icon(i)}</span>{t}</div>' for i, t in d["bens"]
    )
    body = f"""<div class="card">
      <div class="glow"></div>
      <div class="brand" style="left:56px;top:48px;color:rgba(255,255,255,.85)">{d['brand']}</div>
      <h1 class="t">{d['title']}<br><span class="pill">{d['title2']}</span></h1>
      <div class="bens">{bens}</div>
      <div class="prod" style="right:10px;bottom:70px;width:520px;height:820px"><img src="{img(d['cut'])}"></div>
      <div class="round" style="left:56px;bottom:64px;width:210px;height:210px;background:#fff;color:{c1}"><b>{d['badge'][0]}</b><small>{d['badge'][1]}</small></div>
      {f'<div class="sticker" style="right:44px;top:44px;background:#ffd400;color:#1b1b1b;transform:rotate(4deg)">{d["sticker"]}</div>' if d.get('sticker') else ''}
    </div>"""
    css = f""".card{{background:linear-gradient(160deg,{c1} 0%,{c2} 100%)}}
    .glow{{position:absolute;right:-120px;bottom:120px;width:760px;height:760px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.45),rgba(255,255,255,0) 65%)}}
    .t{{position:absolute;left:56px;top:104px;right:40px;color:#fff;font-size:{d.get('size', 112)}px;text-shadow:0 6px 24px rgba(0,0,0,.18)}}
    .pill{{display:inline-block;margin-top:14px;padding:10px 26px 8px;border-radius:22px;background:#fff;color:{c1};font-size:.62em;letter-spacing:-.01em}}
    .bens{{position:absolute;left:56px;top:470px;display:grid;gap:18px;width:380px}}
    .ben{{background:rgba(255,255,255,.94);color:#1c1c1c;box-shadow:0 10px 30px -12px rgba(0,0,0,.35)}}"""
    return page(body, css)


def t_scene(d):
    """Тёмная сцена с цветным свечением, белый заголовок, чек-лист справа, товар по центру-слева."""
    c1, c2, acc = d["colors"]
    bens = "".join(
        f'<div class="ben"><span class="ic" style="background:{acc}">{icon(i, "#111")}</span>{t}</div>'
        for i, t in d["bens"]
    )
    body = f"""<div class="card">
      <div class="halo"></div><div class="floor"></div>
      <h1 class="t">{d['title']}<br><span style="color:{acc}">{d['title2']}</span></h1>
      <div class="prod" style="left:40px;bottom:120px;width:520px;height:760px"><img src="{img(d['cut'])}"></div>
      <div class="bens">{bens}</div>
      <div class="round" style="right:56px;bottom:70px;width:200px;height:200px;background:{acc};color:#111"><b>{d['badge'][0]}</b><small>{d['badge'][1]}</small></div>
      <div class="brand" style="left:56px;bottom:60px;color:rgba(255,255,255,.55)">{d['brand']}</div>
    </div>"""
    css = f""".card{{background:radial-gradient(120% 90% at 30% 60%,{c1} 0%,{c2} 70%)}}
    .halo{{position:absolute;left:-60px;top:360px;width:720px;height:720px;border-radius:50%;background:radial-gradient(circle,{acc}66,transparent 62%)}}
    .floor{{position:absolute;left:0;right:0;bottom:0;height:260px;background:linear-gradient(transparent,rgba(0,0,0,.45))}}
    .t{{position:absolute;left:56px;top:70px;right:56px;color:#fff;font-size:{d.get('size', 104)}px}}
    .bens{{position:absolute;right:48px;top:470px;display:grid;gap:16px;width:330px}}
    .ben{{flex-direction:column;align-items:flex-start;gap:10px;padding:18px 20px;background:rgba(255,255,255,.1);border:1.5px solid rgba(255,255,255,.22);color:#fff;font-size:25px;backdrop-filter:blur(6px)}}
    .ben .ic{{width:52px;height:52px}}"""
    return page(body, css)


def t_clean(d):
    """Светлая «аптечная» подача: цветной заголовок, лента-ярлык, товар крупно, бейджи по углам."""
    c1, c2, acc = d["colors"]
    tags = "".join(f'<span class="tag">{icon(i, acc, 30)}{t}</span>' for i, t in d["bens"][:3])
    body = f"""<div class="card">
      <div class="dots"></div>
      <h1 class="t">{d['title']}</h1>
      <div class="sub">{d['title2']}</div>
      <div class="ribbon">{d.get('ribbon', d['bens'][0][1])}</div>
      <div class="prod" style="left:110px;right:110px;bottom:190px;height:700px"><img src="{img(d['cut'])}"></div>
      <div class="tags">{tags}</div>
      <div class="round" style="right:50px;top:330px;width:190px;height:190px;background:{c1};color:#fff;box-shadow:0 16px 40px -16px {c1}"><b>{d['badge'][0]}</b><small>{d['badge'][1]}</small></div>
    </div>"""
    css = f""".card{{background:linear-gradient(180deg,#ffffff 0%,{c2} 100%)}}
    .dots{{position:absolute;inset:0;background-image:radial-gradient({c1}22 2px,transparent 2.5px);background-size:34px 34px;mask-image:linear-gradient(transparent 30%,#000)}}
    .t{{position:absolute;left:56px;right:56px;top:64px;color:{c1};font-size:{d.get('size', 108)}px}}
    .sub{{position:absolute;left:60px;top:{64 + int(d.get('size', 108) * 0.95) + 16}px;font-weight:700;font-size:36px;color:#2a2a2a}}
    .ribbon{{position:absolute;left:0;top:{64 + int(d.get('size', 108) * 0.95) + 84}px;padding:14px 34px 14px 56px;background:{acc};color:#fff;font-weight:900;font-size:30px;text-transform:uppercase;border-radius:0 40px 40px 0}}
    .tags{{position:absolute;left:40px;right:40px;bottom:50px;display:flex;justify-content:center;gap:14px}}
    .tag{{display:flex;align-items:center;gap:10px;padding:16px 20px;border-radius:20px;background:#fff;font-weight:800;font-size:24px;color:#1c1c1c;box-shadow:0 10px 26px -14px rgba(0,0,0,.35)}}"""
    return page(body, css)


def t_offer(d):
    """Акция: насыщенный фон с лучами, гигантская скидка, лента «Новинка», товар с тенью."""
    c1, c2, acc = d["colors"]
    body = f"""<div class="card">
      <div class="rays"></div>
      <div class="sticker" style="left:50px;top:50px;background:#fff;color:{c1};transform:rotate(-3deg)">{d.get('sticker', 'НОВИНКА')}</div>
      <div class="sale">{d['sale']}</div>
      <h1 class="t">{d['title']}<br>{d['title2']}</h1>
      <div class="prod" style="left:190px;right:40px;bottom:40px;height:720px"><img src="{img(d['cut'])}"></div>
      <div class="round" style="left:50px;bottom:120px;width:220px;height:220px;background:{acc};color:#1b1b1b;transform:rotate(-8deg)"><b>{d['badge'][0]}</b><small>{d['badge'][1]}</small></div>
    </div>"""
    css = f""".card{{background:radial-gradient(90% 70% at 60% 65%,{c2} 0%,{c1} 70%)}}
    .rays{{position:absolute;inset:-200px;background:repeating-conic-gradient(from 0deg at 60% 62%,rgba(255,255,255,.09) 0 8deg,transparent 8deg 18deg)}}
    .sale{{position:absolute;right:46px;top:36px;font-weight:900;font-size:190px;line-height:1;color:{acc};letter-spacing:-.05em;text-shadow:0 10px 30px rgba(0,0,0,.25)}}
    .t{{position:absolute;left:52px;top:250px;right:40px;color:#fff;font-size:{d.get('size', 84)}px}}"""
    return page(body, css)


TEMPLATES = {"infographic": t_infographic, "scene": t_scene, "clean": t_clean, "offer": t_offer}

# ------------------------------------------------------------ рендер и сид


def render(chrome: str, name: str, html: str) -> Path:
    HTML.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    page_file = HTML / f"{name}.html"
    page_file.write_text(html, "utf-8")
    png = OUT / f"{name}.png"
    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=900,1200",
            "--virtual-time-budget=6000",
            "--allow-file-access-from-files",
            f"--screenshot={png}",
            page_file.as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return png


def install_seed(sets: dict) -> None:
    """Кладёт обложки в backend/seed и пишет manifest.json.
    Поднимите rev в sets.json — и уже работающие установки обновят картинки при старте."""
    shutil.rmtree(SEED, ignore_errors=True)
    manifest = []
    for slug, s in sets.items():
        (SEED / slug).mkdir(parents=True)
        item = {
            "slug": slug,
            "rev": s["rev"],
            "title": s["title"],
            "description": s["description"],
            "context": s["context"],
            "variants": [],
            "competitors": [],
        }
        for role, cards in (("variant", s["variants"]), ("competitor", s["competitors"])):
            for i, card in enumerate(cards, 1):
                rel = f"{slug}/{role}-{i}.jpg"
                picture = Image.open(OUT / f"{slug}-{role}-{i}.png").convert("RGB")
                picture.resize((720, 960), Image.LANCZOS).save(SEED / rel, quality=88, optimize=True)
                entry = {"file": rel, "title": card["name"]} if role == "variant" else {"file": rel}
                item[f"{role}s"].append(entry)
        manifest.append(item)
    (SEED / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (SEED / "CREDITS.md").write_text(CREDITS, "utf-8")
    print(f"Сид обновлён: {SEED}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sets", nargs="*", help="слаги наборов (по умолчанию все)")
    parser.add_argument("--seed", action="store_true", help="записать результат в backend/seed")
    args = parser.parse_args()

    sets = json.loads((HERE / "sets.json").read_text("utf-8"))
    chrome = find_chrome()
    for slug in args.sets or list(sets):
        for role, cards in (("variant", sets[slug]["variants"]), ("competitor", sets[slug]["competitors"])):
            for i, card in enumerate(cards, 1):
                print(render(chrome, f"{slug}-{role}-{i}", TEMPLATES[card["t"]](card)).name, flush=True)
    if args.seed:
        install_seed(sets)


if __name__ == "__main__":
    main()
