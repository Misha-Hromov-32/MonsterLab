"""Общие модели запросов."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductContext(BaseModel):
    """Что известно о товаре — помогает экспертному разбору, в анализе внимания не участвует."""

    query: str = Field("", max_length=120)
    category: str = Field("", max_length=80)
    price: str = Field("", max_length=20)
    audience: str = Field("", max_length=80)
    # бренд и позиционирование: «премиум, эко», «бюджетно для студентов» — визуальный разбор сверяет с ним обложку
    positioning: str = Field("", max_length=160)
