"""Проверки возвращают место, фрагмент и действие. Окончательное решение принимает площадка."""

import io
import os
import re
import subprocess
import threading

import cv2
import numpy as np

SOURCES = {
    "wb": "https://seller.wildberries.ru/instructions/material/A-927",
    "ozon": "https://docs.ozon.ru/global/products/requirements/media/image-requirements/",
}
OCR_SLOTS = threading.BoundedSemaphore(2)
RULES = (
    (
        r"(?<!\w)(?:№\s*1|номер\s+(?:один|1))(?!\d|\w)",
        "Заявление о лидерстве",
        "Уточните контекст. Номер оттенка или модели может быть частью маркировки.",
    ),
    (
        r"\b(?:лучш(?:ий|ая|ее|ие|их|его|ую)|(?:хит|топ|лидер)\s+продаж)\b",
        "Оценочное суждение",
        "Замените рекламную оценку проверяемым свойством товара.",
    ),
    (
        r"(?:https?://|www\.|t\.me/|vk\.com/)\S+|(?<![\w.+-])[\w.+-]{1,64}@[\w.-]{1,190}\.[a-zа-я]{2,24}",
        "Внешняя ссылка или контакт",
        "Проверьте адрес и уберите контакты продавца из карточки.",
    ),
    (
        r"(?<!\w)(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)",
        "Номер телефона",
        "Проверьте, не попал ли на карточку телефон продавца.",
    ),
    (
        r"\bскидк[аиуеой]+\b|\b\d[\d \u00a0]{0,7}\s*(?:₽|руб(?:лей|ля)?\b)",
        "Цена или скидка",
        "Проверьте рекламную надпись. Цену указывают в предназначенном для неё поле.",
    ),
)


def finding(field, match, reason, action, level="review"):
    return {"field": field, "match": match, "reason": reason, "action": action, "level": level}


def check(market: str, **fields: str) -> list:
    results = []
    for field, value in fields.items():
        for pattern, reason, action in RULES:
            match = re.search(pattern, value, re.I)
            if not match:
                continue
            # В описании и в обозначениях моделей важен контекст. По Ozon замечания требуют сверки с категорией.
            level = "rule" if market == "wb" and field == "Обложка" and reason != "Заявление о лидерстве" else "review"
            results.append(finding(field, match.group(), reason, action, level))
    if market == "wb" and len(fields.get("Название", "")) > 60:
        results.append(
            finding("Название", "", "Больше 60 символов", "Сократите наименование товара до 60 символов.", "rule")
        )
    return results


def inspect_cover(market: str, image, size: int) -> list:
    issues = []
    if size > 10 * 1024 * 1024:
        issues.append(
            finding("Обложка", "", "Размер файла больше 10 МБ", "Уменьшите размер файла перед загрузкой.", "rule")
        )
    if market == "wb":
        detected, _ = cv2.QRCodeDetector().detect(np.asarray(image))
        if detected:
            issues.append(finding("Обложка", "QR", "QR-код", "Уберите QR-код с изображения.", "rule"))
    return issues


def read_cover(image) -> tuple[str, str]:
    with io.BytesIO() as buf:
        image.save(buf, format="PNG")
        with OCR_SLOTS:
            try:
                result = subprocess.run(
                    [os.getenv("TESSERACT_CMD") or "tesseract", "stdin", "stdout", "-l", "rus+eng", "--psm", "11"],
                    input=buf.getvalue(),
                    capture_output=True,
                    timeout=25,
                    check=True,
                )
            except (OSError, subprocess.SubprocessError):
                return "", "Распознавание недоступно. Проверьте надписи вручную."
    text = result.stdout.decode("utf-8", "replace").strip()
    return text, "Текст распознан" if text else "Текст не распознан. Проверьте обложку вручную."
