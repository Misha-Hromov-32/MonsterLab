"""Единый формат ошибок API: {"detail": {"code": "...", "message": "понятный текст"}}.

code — для кода фронтенда (например, image_expired → загрузить картинку заново),
message — готовая фраза для пользователя, по-русски.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .services.uploads import ImageExpired

log = logging.getLogger(__name__)

# Подписи полей запросов — чтобы ошибка валидации читалась человеком, а не «context.price».
FIELD_NAMES = {
    "file": "файл",
    "files": "файлы",
    "id": "картинка",
    "variants": "варианты",
    "competitors": "конкуренты",
    "layout": "раскладка",
    "role": "тип картинок",
    "query": "поисковый запрос",
    "category": "категория",
    "price": "цена",
    "audience": "аудитория",
    "title": "название",
    "title_muted": "вторая строка заголовка",
    "description": "описание",
    "eyebrow": "надзаголовок",
    "lead": "подзаголовок",
    "cta": "текст кнопки",
    "text": "текст",
    "steps": "шаги",
    "design": "дизайн",
    "password": "пароль",
    "api_key": "ключ API",
    "base_url": "адрес API",
    "models": "модели",
    "ids": "порядок",
    "hero": "обложка для главной",
}

# Ответы на ошибки, которые возникают до наших обработчиков (нет такого адреса, не тот метод).
STATUS_MESSAGES = {
    400: ("bad_request", "Некорректный запрос"),
    404: ("not_found", "Не найдено"),
    405: ("method_not_allowed", "Этот метод здесь не поддерживается"),
    413: ("too_large", "Слишком большой запрос"),
}


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def _field(loc: tuple) -> str:
    names = [FIELD_NAMES.get(str(p)) for p in reversed(loc) if not isinstance(p, int)]
    return next((n for n in names if n), "запрос")


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        field = _field(tuple(errors[0].get("loc", ()))) if errors else "запрос"
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "bad_request", "message": f"Проверьте поле «{field}»"}},
        )

    @app.exception_handler(ImageExpired)
    async def _expired(_: Request, exc: ImageExpired) -> JSONResponse:
        # фронтенд по этому коду молча загружает картинку заново
        message = "Изображение не найдено, загрузите его заново"
        return JSONResponse(status_code=404, content={"detail": {"code": "image_expired", "message": message}})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Необработанная ошибка", exc_info=exc)
        message = "Что-то пошло не так. Попробуйте ещё раз."
        return JSONResponse(status_code=500, content={"detail": {"code": "internal", "message": message}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):  # уже в нашем формате — из api_error
            detail = exc.detail
        else:
            code, message = STATUS_MESSAGES.get(exc.status_code, ("error", "Что-то пошло не так"))
            detail = {"code": code, "message": message}
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
