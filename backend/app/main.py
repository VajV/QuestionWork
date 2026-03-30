"""
QuestionWork Backend - FastAPI Application
IT-фриланс биржа с RPG-геймификацией
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time

import re

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.logging_config import setup_logging
from app.core.config import settings
from app.core.redis_client import close_redis_client, get_redis_client

logger = logging.getLogger(__name__)

# ── Request context ContextVars ─────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
request_user_var: ContextVar[str] = ContextVar("request_user", default="-")


def _build_cors_origins() -> list[str]:
    raw_frontend_urls = os.getenv("FRONTEND_URL", settings.FRONTEND_URL)
    origins = {
        origin.strip().rstrip("/")
        for origin in raw_frontend_urls.split(",")
        if origin.strip()
    }
    if settings.APP_ENV.lower() in ("development", "dev"):
        origins.update({
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3001", "http://127.0.0.1:3001",
        })
    return sorted(origins)

# Initialize Sentry if DSN is provided
try:
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=float(settings.SENTRY_TRACES_SAMPLE_RATE or 0.0),
            environment=settings.APP_ENV,
        )
except Exception:
    # Do not fail startup if Sentry initialization fails; log is handled by logging_config
    pass

# OpenTelemetry initialization (optional)
try:
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
        sampler = TraceIdRatioBased(float(settings.OTEL_SAMPLE_RATE or 0.0))
        provider = TracerProvider(resource=resource, sampler=sampler)
        trace.set_tracer_provider(provider)

        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
except Exception:
    # Do not break startup when OpenTelemetry packages are not installed or initialization fails
    pass

# Загружаем переменные окружения
load_dotenv()

from app.api.v1.api import api_router
from app.api.v1.endpoints.ws import ws_router
from app.core.ws_manager import ws_manager
from app.db.session import close_db_pool, init_db_pool


# Initialize structured logging
setup_logging()

# Prometheus metrics
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram("http_request_latency_seconds", "Request latency seconds", ["path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Note: SECRET_KEY and all critical env vars are validated at import time
    # by app.core.config._validate_settings(). No additional check needed here.
    # Инициализация пула БД при запуске
    await init_db_pool()
    # Pre-warm learning voice intro cache in background (non-blocking)
    try:
        from app.services.learning_voice_service import warmup_intro_cache
        asyncio.ensure_future(warmup_intro_cache())
    except Exception:
        pass
    yield
    # Закрытие WS-соединений
    await ws_manager.close_all()
    # Закрытие пула при остановке
    await close_db_pool()
    await close_redis_client()


# ── Custom JSON encoder for Decimal values ──────────────────────
from decimal import Decimal
from fastapi.responses import ORJSONResponse
import json as _json

class DecimalSafeEncoder(_json.JSONEncoder):
    """Encode Decimal as string to preserve precision."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class DecimalJSONResponse(Response):
    media_type = "application/json"

    def render(self, content) -> bytes:
        return _json.dumps(content, cls=DecimalSafeEncoder).encode("utf-8")


# Создаём FastAPI приложение
_is_dev = os.getenv("APP_ENV", "development").lower() in ("development", "dev")
app = FastAPI(
    title=os.getenv("APP_NAME", "QuestionWork"),
    description="Backend для IT-фриланс биржи с RPG-геймификацией",
    version="0.1.0",
    debug=os.getenv("DEBUG", "False") == "True",
    lifespan=lifespan,
    default_response_class=DecimalJSONResponse,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Try to instrument FastAPI and Redis if instrumentation packages are installed
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass

    try:
        RedisInstrumentor().instrument()
    except Exception:
        pass
except Exception:
    # Instrumentation packages not installed; continue without auto-instrumentation
    pass

# Instrument asyncpg if the package is installed
try:
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    AsyncPGInstrumentor().instrument()
except Exception:
    pass


# Tracing middleware: create a span per HTTP request if OpenTelemetry is available
@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("questionwork")
        method = request.method
        path = request.url.path
        with tracer.start_as_current_span(f"HTTP {method} {path}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.route", path)
            # L-07: Propagate X-Request-ID into OTEL span
            request_id = request.headers.get("X-Request-ID")
            if request_id:
                span.set_attribute("http.request_id", request_id)
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            return response
    except ImportError:
        # OpenTelemetry not installed — bypass tracing
        return await call_next(request)
    except Exception:
        # If tracing fails on an already-dispatched request, re-raise
        # so FastAPI returns error normally. Do NOT call call_next again.
        raise


# Request-context middleware: set request_id and user_id ContextVars
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# Regex to normalize dynamic path segments for Prometheus labels.
# Matches UUIDs, hex IDs (user_abc123), and numeric IDs.
_PATH_ID_RE = re.compile(r"/(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|user_[a-z0-9]+|\d+)(?=/|$)")


def _normalize_path(path: str) -> str:
    """Replace dynamic path segments with {id} to avoid Prometheus label explosion."""
    return _PATH_ID_RE.sub("/{id}", path)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    elapsed = time.time() - start
    path = _normalize_path(request.url.path)
    method = request.method
    status = str(response.status_code)
    try:
        HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(path=path).observe(elapsed)
    except Exception:
        pass
    return response


from app.api.deps import require_admin

@app.get("/metrics", dependencies=[Depends(require_admin)])
def metrics():
    """Prometheus metrics endpoint (admin-only)."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# I-05: Request body size limit (1 MB)
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB


class BodySizeLimitMiddleware:
    def __init__(self, app, *, max_body_size: int):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        content_length = headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except (ValueError, TypeError):
                response = Response(
                    content=json.dumps({"detail": "Invalid Content-Length header"}),
                    status_code=400,
                    media_type="application/json",
                )
                await response(scope, receive, send)
                return
            if declared_length > self.max_body_size:
                response = Response(
                    content=json.dumps({"detail": "Request body too large (max 1 MB)"}),
                    status_code=413,
                    media_type="application/json",
                )
                await response(scope, receive, send)
                return

        total_bytes = 0
        body_limit_exceeded = False
        override_response_sent = False

        async def limited_receive():
            nonlocal total_bytes, body_limit_exceeded
            if body_limit_exceeded:
                return {"type": "http.request", "body": b"", "more_body": False}

            message = await receive()
            if message["type"] == "http.request":
                total_bytes += len(message.get("body", b""))
                if total_bytes > self.max_body_size:
                    body_limit_exceeded = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def tracking_send(message):
            nonlocal override_response_sent
            if body_limit_exceeded:
                if override_response_sent:
                    return
                override_response_sent = True
                response = Response(
                    content=json.dumps({"detail": "Request body too large (max 1 MB)"}),
                    status_code=413,
                    media_type="application/json",
                )
                await response(scope, receive, send)
                return
            await send(message)

        await self.app(scope, limited_receive, tracking_send)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.APP_ENV.lower() in ("production", "prod"):
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.middleware("http")
async def handle_unexpected_exceptions(request: Request, call_next):
    # Catch-all: ensure exceptions become proper Responses so CORSMiddleware
    # (which wraps this HTTP middleware) can still inject CORS headers.
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return Response(
            content=json.dumps({"detail": "Internal server error"}),
            status_code=500,
            media_type="application/json",
        )


# Настраиваем CORS (разрешаем запросы с фронтенда)
app.add_middleware(BodySizeLimitMiddleware, max_body_size=MAX_BODY_SIZE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.APP_ENV.lower() in ("development", "dev")
        else None
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID", "X-TOTP-Token", "X-E2E-Bypass"],
    expose_headers=["X-Response-Text", "X-Script-Length"],
)

# Подключаем роутеры
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)  # WS routes at root level (/ws/...)


# Global unhandled exception handler — prevents leaking stack traces to clients
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json",
    )


# Health check endpoint (pure liveness probe)
@app.get("/health")
async def health_check():
    """Kubernetes liveness probe — only confirms the process is serving HTTP."""
    return {"status": "ok", "message": "QuestionWork API is running"}


# Readiness probe — checks DB & Redis connectivity (cached 10s)
_readiness_cache: dict = {"result": None, "ts": 0.0}
_READINESS_TTL = 10.0

@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe — verifies DB pool and Redis are reachable."""
    now = time.time()
    if _readiness_cache["result"] is not None and (now - _readiness_cache["ts"]) < _READINESS_TTL:
        cached = _readiness_cache["result"]
        return Response(content=cached["body"], status_code=cached["status"], media_type="application/json")

    checks: dict = {}
    shared_state_mode = (
        "degraded-local-allowed"
        if settings.APP_ENV.lower() in {"development", "dev"}
        else "redis-required"
    )
    redis_required = shared_state_mode == "redis-required"

    # DB check
    try:
        from app.db.session import pool as db_pool
        if db_pool is None:
            checks["db"] = "not initialized"
        else:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["db"] = "ok"
            checks["db_pool"] = {
                "size": db_pool.get_size(),
                "idle": db_pool.get_idle_size(),
                "min": db_pool.get_min_size(),
                "max": db_pool.get_max_size(),
            }
    except Exception as e:
        logger.error("Readiness DB check failed: %s", e)
        checks["db"] = "error"

    # Redis check
    try:
        if settings.REDIS_URL:
            client = await get_redis_client(required_in_production=redis_required)
            if client is None:
                raise RuntimeError("Redis client unavailable")
            await client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not configured"
    except Exception as e:
        logger.error("Readiness Redis check failed: %s", e)
        checks["redis"] = "degraded"

    redis_ok = checks.get("redis") == "ok"
    redis_optional = not redis_required and checks.get("redis") in {
        "degraded",
        "not configured",
    }
    all_ok = checks.get("db") == "ok" and (redis_ok or redis_optional)
    status_code = 200 if all_ok else 503
    body = json.dumps(
        {
            "ready": all_ok,
            "checks": checks,
            "shared_state": {
                "mode": shared_state_mode,
                "redis_required": redis_required,
                "status": "ok" if redis_ok else ("degraded" if not redis_required else "unavailable"),
            },
        }
    )
    _readiness_cache["result"] = {"body": body, "status": status_code}
    _readiness_cache["ts"] = time.time()
    return Response(
        content=body,
        status_code=status_code,
        media_type="application/json",
    )


# Root endpoint
@app.get("/")
async def root():
    """Приветственный endpoint"""
    return {
        "message": "Welcome to QuestionWork API",
        "docs": "/docs",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8001)),
        reload=os.getenv("DEBUG", "False") == "True",
    )
