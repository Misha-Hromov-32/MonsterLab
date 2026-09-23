"""Точка входа FastAPI: `uvicorn app.main:app`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config
from .api import admin, analysis, expert, public
from .core import saliency
from .errors import install_handlers
from .services import auth, site

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(saliency.load)  # ~10–20 с на загрузку весов, не блокируем event loop
    await asyncio.to_thread(site.load)  # первый запуск: settings.json и встроенные примеры
    auth.admin_password()  # если пароль не задан — сгенерировать и показать в логе
    yield


app = FastAPI(title="Monster Lab API", version=__version__, lifespan=lifespan)
install_handlers(app)
for module in (analysis, expert, public):
    app.include_router(module.router)
app.include_router(admin.router)
app.include_router(admin.guarded)


# ---------------------------------------------------------------- фронтенд без nginx
# Запуск одним процессом, без Docker и nginx: STATIC_DIR указывает на собранный фронтенд
# (frontend/dist). В Docker эту роль выполняет nginx, и переменная не задаётся.


def _mount_frontend(root: Path) -> None:
    root = root.resolve()
    index = root / "index.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):  # неизвестный адрес API — JSON 404, а не страница
            raise HTTPException(404)
        file = (root / path).resolve()
        if path and file.is_relative_to(root) and file.is_file():
            return FileResponse(file)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


if config.STATIC_DIR and (Path(config.STATIC_DIR) / "index.html").is_file():
    _mount_frontend(Path(config.STATIC_DIR))
