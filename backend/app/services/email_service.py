"""
Transactional e-mail service for QuestionWork.

All public functions are designed to be used as FastAPI BackgroundTasks so
they run after the HTTP response is already sent back to the client.

Config knobs (all optional — set in .env):
    EMAILS_ENABLED   bool  — master switch, default=False (silent in dev)
    SMTP_HOST        str   — e.g. "smtp.sendgrid.net"
    SMTP_PORT        int   — 587 (STARTTLS) or 465 (SSL)
    SMTP_USER        str
    SMTP_PASSWORD    str
    SMTP_FROM        str   — "QuestionWork <noreply@questionwork.io>"
    SMTP_TLS         bool  — True → STARTTLS, False → plain / SSL port

Usage (inside a FastAPI endpoint):
    background_tasks.add_task(
        email_service.send_quest_assigned,
        to="user@example.com",
        username="Alice",
        quest_title="Fix CI pipeline",
    )
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as html_escape
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────

def _build_message(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send(msg: MIMEMultipart) -> None:
    """Low-level SMTP send — called synchronously inside a background task."""
    to = msg["To"]
    try:
        ctx = ssl.create_default_context()
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.starttls(context=ctx)
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())
        else:
            # Port 465 — implicit SSL
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx, timeout=15) as smtp:
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())
        logger.info("Email sent to %s | subject=%s", to, msg["Subject"])
    except Exception as exc:
        logger.error("Email send failed to %s: %s", to, exc)


def _enabled() -> bool:
    if not settings.EMAILS_ENABLED:
        return False
    if not settings.SMTP_HOST:
        logger.debug("EMAILS_ENABLED=true but SMTP_HOST is empty — skipping send")
        return False
    return True


# ── Public API ─────────────────────────────────────────────────────────────

def send_quest_assigned(to: str, username: str, quest_title: str) -> None:
    """Notify a freelancer that they have been assigned to a quest."""
    if not _enabled():
        return
    # P0-09 FIX: escape user-controlled values to prevent HTML injection
    safe_user = html_escape(username)
    safe_title = html_escape(quest_title)
    subject = f"[QuestionWork] Вас назначили на квест: {safe_title}"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:#7c3aed;">⚔️ Новый квест!</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Клиент назначил вас исполнителем квеста:</p>
      <blockquote style="border-left:4px solid #7c3aed;padding-left:12px;color:#a78bfa;">
        {safe_title}
      </blockquote>
      <p>Войдите в <a href="{html_escape(settings.FRONTEND_URL)}/marketplace" style="color:#7c3aed;">QuestionWork</a>,
         чтобы приступить к выполнению.</p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        f"Вас назначили исполнителем квеста «{quest_title}».\n"
        "Откройте QuestionWork, чтобы приступить.\n"
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_quest_confirmed(
    to: str,
    username: str,
    quest_title: str,
    reward: int = 0,
    xp_awarded: int = 0,
) -> None:
    """Notify a freelancer that the client confirmed quest completion."""
    if not _enabled():
        return
    safe_user = html_escape(username)
    safe_title = html_escape(quest_title)
    subject = f"[QuestionWork] Квест подтверждён: {safe_title}"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:#10b981;">🏆 Квест завершён!</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Клиент подтвердил выполнение квеста:</p>
      <blockquote style="border-left:4px solid #10b981;padding-left:12px;color:#6ee7b7;">
        {safe_title}
      </blockquote>
      <ul>
        <li>💰 Награда: <strong>{int(reward)} монет</strong></li>
        <li>✨ XP: <strong>+{int(xp_awarded)}</strong></li>
      </ul>
      <p><a href="{html_escape(settings.FRONTEND_URL)}/profile" style="color:#10b981;">Открыть профиль</a></p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        f"Квест «{quest_title}» подтверждён клиентом.\n"
        f"Награда: {reward} монет | XP: +{xp_awarded}\n"
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_review_received(
    to: str,
    username: str,
    reviewer_username: str,
    rating: int,
    comment: Optional[str] = None,
) -> None:
    """Notify a user that they received a new review."""
    if not _enabled():
        return
    safe_user = html_escape(username)
    safe_reviewer = html_escape(reviewer_username)
    safe_comment = html_escape(comment) if comment else None
    stars = "⭐" * rating
    subject = f"[QuestionWork] Новый отзыв от {safe_reviewer}"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:#f59e0b;">📝 Вы получили отзыв!</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Пользователь <strong>{safe_reviewer}</strong> оставил отзыв:</p>
      <p style="font-size:1.4em;">{stars}</p>
      {f'<blockquote style="border-left:4px solid #f59e0b;padding-left:12px;color:#fcd34d;">{safe_comment}</blockquote>' if safe_comment else ""}
      <p><a href="{html_escape(settings.FRONTEND_URL)}/profile" style="color:#f59e0b;">Посмотреть профиль</a></p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        f"{reviewer_username} оставил отзыв: {stars}\n"
        + (f"{comment}\n" if comment else "")
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_quest_completed(to: str, username: str, quest_title: str, xp_gained: int = 0) -> None:
    """Send quest-completed notification (delegates to send_quest_confirmed)."""
    send_quest_confirmed(to=to, username=username, quest_title=quest_title, xp_awarded=xp_gained)


def send_welcome(to: str, username: str) -> None:
    """Send a welcome email to a newly registered user."""
    if not _enabled():
        return
    safe_user = html_escape(username)
    frontend = html_escape(settings.FRONTEND_URL)
    subject = "[QuestionWork] Добро пожаловать!"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:#7c3aed;">🎉 Добро пожаловать в QuestionWork!</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Ваш аккаунт создан. Заполните профиль и начните принимать квесты — зарабатывайте XP и прокачивайте свой грейд.</p>
      <p><a href="{frontend}/profile/setup" style="color:#7c3aed;">Настроить профиль</a></p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        "Добро пожаловать в QuestionWork! Заполните профиль и начните принимать квесты.\n"
        f"{settings.FRONTEND_URL}/profile/setup\n"
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_password_reset(to: str, username: str, reset_link: str) -> None:
    """Send a password reset email with a secure link."""
    if not _enabled():
        return
    safe_user = html_escape(username)
    safe_link = html_escape(reset_link)
    subject = "[QuestionWork] Сброс пароля"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:#ef4444;">🔑 Сброс пароля</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Вы запросили сброс пароля. Перейдите по ссылке ниже для создания нового пароля:</p>
      <p><a href="{safe_link}" style="color:#ef4444;font-weight:bold;">Сбросить пароль</a></p>
      <p style="color:#999;">Ссылка действительна 30 минут. Если вы не запрашивали сброс — проигнорируйте это письмо.</p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        "Вы запросили сброс пароля. Перейдите по ссылке:\n"
        f"{reset_link}\n\n"
        "Ссылка действительна 30 минут.\n"
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_withdrawal_status(to: str, username: str, amount: str, currency: str, status: str) -> None:
    """Notify a user about withdrawal status change."""
    if not _enabled():
        return
    safe_user = html_escape(username)
    status_label = {"approved": "одобрен", "rejected": "отклонён", "processing": "обрабатывается"}.get(status, status)
    status_color = {"approved": "#10b981", "rejected": "#ef4444"}.get(status, "#f59e0b")
    subject = f"[QuestionWork] Вывод средств: {status_label}"
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <h2 style="color:{status_color};">💳 Вывод средств</h2>
      <p>Привет, <strong>{safe_user}</strong>!</p>
      <p>Статус вашего запроса на вывод <strong>{html_escape(amount)} {html_escape(currency)}</strong>:</p>
      <p style="font-size:1.2em;color:{status_color};font-weight:bold;">{html_escape(status_label)}</p>
      <p><a href="{html_escape(settings.FRONTEND_URL)}/profile" style="color:#7c3aed;">Открыть профиль</a></p>
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.</small>
    </body></html>
    """
    text_body = (
        f"Привет, {username}!\n\n"
        f"Вывод {amount} {currency}: {status_label}\n"
    )
    _send(_build_message(to, subject, html_body, text_body))


def send_lifecycle_nudge(to: str, username: str, subject: str, body_html: str) -> None:
    """Send a generic lifecycle nudge email with a custom subject and HTML body.

    NOTE: ``body_html`` is injected raw — the caller is responsible for sanitising it.
    ``username`` and ``subject`` are escaped here.
    """
    if not _enabled():
        return
    safe_user = html_escape(username)
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#e0e0e0;background:#0d1117;padding:24px;">
      <p>Привет, <strong>{safe_user}</strong>!</p>
      {body_html}
      <hr style="border-color:#333;"/>
      <small style="color:#666;">Это автоматическое сообщение — не отвечайте на него.
      <a href="{html_escape(settings.FRONTEND_URL)}/profile" style="color:#7c3aed;"> Отписаться</a></small>
    </body></html>
    """
    text_body = f"Привет, {username}!\n\n(Для читаемой версии откройте это письмо в браузере.)\n"
    _send(_build_message(to, subject, html_body, text_body))
