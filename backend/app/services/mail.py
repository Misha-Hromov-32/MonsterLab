"""Письма покупателям: подтверждение email и сброс пароля.

Письмо — HTML по шаблону templates/email/letter.html (таблицы и стили в атрибутах: так его одинаково
показывают Gmail, Яндекс, Mail.ru и Outlook) плюс текстовая версия для клиентов без HTML.
Логотип вложен в само письмо (cid:logo) — он виден, даже когда внешние картинки заблокированы.

Отправка — SMTP из переменных SMTP_*. Без SMTP_HOST письма не уходят, а пишутся в журнал
вместе со ссылкой — так можно проверить регистрацию локально.
"""

from __future__ import annotations

import html
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from .. import config

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "email"
VERIFY_TTL_HOURS = 24
RESET_TTL_HOURS = 1


class MailError(RuntimeError):
    """Письмо не ушло: почтовый сервер недоступен или отказал."""


def enabled() -> bool:
    return bool(config.SMTP_HOST and config.MAIL_FROM)


# ---------------------------------------------------------------- шаблон


@cache
def _template(name: str) -> str:
    return (TEMPLATES / name).read_text("utf-8")


def _render(name: str, values: dict[str, str]) -> str:
    """{{ ключ }} → значение. Всё экранируется, кроме ключей с суффиксом _html — это готовая разметка."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        value = values[key]
        return value if key.endswith("_html") else html.escape(value)

    return re.sub(r"{{\s*(\w+)\s*}}", sub, _template(name))


def _site() -> str:
    return urlsplit(config.PUBLIC_URL).netloc or config.PUBLIC_URL


def _letter(to: str, subject: str, letter: dict[str, str], text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.MAIL_FROM_NAME, config.MAIL_FROM or "no-reply@localhost"))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(config.MAIL_FROM.rpartition("@")[2] or None))
    msg["Auto-Submitted"] = "auto-generated"  # автоответчики не отвечают на такие письма
    msg.set_content(text)
    values = {"subject": subject, "site": _site(), "site_url": config.PUBLIC_URL, "features_html": "", **letter}
    msg.add_alternative(_render("letter.html", values), subtype="html")
    msg.get_payload()[1].add_related((TEMPLATES / "logo.png").read_bytes(), "image", "png", cid="<logo>")
    return msg


def verification_letter(to: str, link: str) -> EmailMessage:
    letter = {
        "preheader": "Подтвердите почту — и можно проверять обложки",
        "eyebrow": "Подтверждение почты",
        "title": "Остался один шаг",
        "lead": f"Вы зарегистрировались в MonStoreLab с адресом {to}. "
        "Подтвердите, что это ваша почта, — и сразу откроются разбор обложек, тест полки и примеры.",
        "button": "Подтвердить почту",
        "link": link,
        "note": f"Ссылка действует {VERIFY_TTL_HOURS} часа. Если вы не регистрировались в MonStoreLab, "
        "просто удалите это письмо: без подтверждения аккаунт не заработает.",
        "features_html": _template("features.html"),
    }
    text = (
        "Остался один шаг\n\n"
        f"Вы зарегистрировались в MonStoreLab с адресом {to}.\n"
        f"Подтвердите почту по ссылке:\n{link}\n\n"
        f"Ссылка действует {VERIFY_TTL_HOURS} часа. Если вы не регистрировались — просто удалите это письмо.\n\n"
        f"— MonStoreLab, {config.PUBLIC_URL}\n"
    )
    return _letter(to, "Подтвердите почту для MonStoreLab", letter, text)


def reset_letter(to: str, link: str) -> EmailMessage:
    letter = {
        "preheader": "Ссылка для нового пароля — действует час",
        "eyebrow": "Сброс пароля",
        "title": "Новый пароль в один клик",
        "lead": f"Для аккаунта {to} запросили сброс пароля. Нажмите кнопку и задайте новый — "
        "после этого на всех устройствах нужно будет войти заново.",
        "button": "Задать новый пароль",
        "link": link,
        "note": f"Ссылка действует {RESET_TTL_HOURS} час и сработает один раз. "
        "Если вы не запрашивали сброс — ничего не делайте, пароль останется прежним.",
    }
    text = (
        "Новый пароль в один клик\n\n"
        f"Для аккаунта {to} запросили сброс пароля. Задайте новый по ссылке:\n{link}\n\n"
        f"Ссылка действует {RESET_TTL_HOURS} час. Если вы не запрашивали сброс — ничего не делайте.\n\n"
        f"— MonStoreLab, {config.PUBLIC_URL}\n"
    )
    return _letter(to, "Сброс пароля MonStoreLab", letter, text)


# ---------------------------------------------------------------- отправка


def deliver(msg: EmailMessage) -> None:
    """Отправляет письмо по SMTP. Тесты подменяют эту функцию и складывают письма в список."""
    if not enabled():
        body = msg.get_body(("plain",))
        log.warning("SMTP не настроен — письмо не отправлено:\n%s", body.get_content() if body else msg["Subject"])
        return
    timeout = 20
    try:
        if config.SMTP_SECURITY == "ssl":
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=timeout, context=_tls())
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=timeout)
        with server:
            if config.SMTP_SECURITY == "starttls":
                server.starttls(context=_tls())
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        log.error("Письмо «%s» не отправлено: %s", msg["Subject"], exc)
        raise MailError("Не удалось отправить письмо. Попробуйте через пару минут.") from exc


def _tls() -> ssl.SSLContext:
    return ssl.create_default_context()  # проверка сертификата почтового сервера обязательна
