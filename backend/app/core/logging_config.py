"""
Logging configuration: structured JSON-like logs.

Комментарии на русском; формат логов упрощённый JSON строк.
"""
import logging
import json
from typing import Any

from app.core.config import settings


class SimpleJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Inject request-scoped context when available
        try:
            from app.main import request_id_var, request_user_var
            rid = request_id_var.get("-")
            uid = request_user_var.get("-")
            if rid != "-":
                payload["request_id"] = rid
            if uid != "-":
                payload["user_id"] = uid
        except Exception:
            pass
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except Exception:
            return json.dumps({"message": record.getMessage()})


def setup_logging() -> None:
    """Configure root logger with SimpleJsonFormatter.

    Это вызывается при старте приложения.
    """
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(SimpleJsonFormatter())

    root = logging.getLogger()
    # Avoid duplicate handlers when reloading in dev
    if not any(isinstance(h, type(handler)) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(level)
