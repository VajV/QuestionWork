"""
app/core/alerts.py — Centralised alerting helpers for cron / operational scripts.

Supports:
- Sentry: captures exceptions (when SENTRY_DSN is set)
- Slack: posts messages to an incoming-webhook URL (when SLACK_WEBHOOK_URL is set)

Both channels are opt-in via environment variables so the functions are safe to
call unconditionally — they simply no-op when not configured.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger("questionwork.alerts")


# ───────────────────────────────────────────────────────────────────────
# Sentry
# ───────────────────────────────────────────────────────────────────────

def capture_exception(exc: BaseException, extra: Optional[dict] = None) -> None:
    """Report an exception to Sentry (no-op when sentry_sdk is not configured)."""
    try:
        import sentry_sdk  # noqa: PLC0415
        if extra:
            with sentry_sdk.new_scope() as scope:
                for k, v in extra.items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)
    except Exception:  # sentry not installed or not init'd
        logger.debug("Sentry not available; exception not forwarded", exc_info=True)


def capture_message(message: str, level: str = "info") -> None:
    """Send an informational message to Sentry."""
    try:
        import sentry_sdk  # noqa: PLC0415
        sentry_sdk.capture_message(message, level=level)
    except Exception:
        logger.debug("Sentry not available; message not forwarded")


# ───────────────────────────────────────────────────────────────────────
# Slack
# ───────────────────────────────────────────────────────────────────────

def _slack_post(webhook_url: str, text: str) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status not in (200, 204):
                logger.warning(f"Slack webhook returned status {resp.status}")
    except urllib.error.URLError as exc:
        logger.warning(f"Slack webhook call failed: {exc}")


def slack_notify(message: str, webhook_url: Optional[str] = None) -> None:
    """Post a message to Slack.

    ``webhook_url`` defaults to ``settings.SLACK_WEBHOOK_URL`` when omitted.
    No-op if neither is set.
    """
    url = webhook_url
    if not url:
        try:
            from app.core.config import settings as _settings  # noqa: PLC0415
            url = _settings.SLACK_WEBHOOK_URL
        except Exception:
            pass

    if not url:
        return

    try:
        _slack_post(url, message)
    except Exception as exc:
        logger.warning(f"Failed to post Slack notification: {exc}")


def slack_error(title: str, detail: str, webhook_url: Optional[str] = None) -> None:
    """Post a red-block (error-formatted) message to Slack."""
    text = f":rotating_light: *{title}*\n```{detail}```"
    slack_notify(text, webhook_url=webhook_url)


def slack_ok(title: str, detail: str = "", webhook_url: Optional[str] = None) -> None:
    """Post a green-check (success-formatted) message to Slack."""
    text = f":white_check_mark: *{title}*"
    if detail:
        text += f"\n{detail}"
    slack_notify(text, webhook_url=webhook_url)
