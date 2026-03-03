"""
QuestionWork Backend - FastAPI Application
IT-фриланс биржа с RPG-геймификацией
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.logging_config import setup_logging
from app.core.config import settings

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
from app.db.session import close_db_pool, engine, init_db_pool


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
    # Инициализация пула БД при запуске
    await init_db_pool()
    yield
    # Закрытие пула при остановке
    await close_db_pool()
    # Dispose SQLAlchemy engine for clean shutdown
    await engine.dispose()


# Создаём FastAPI приложение
app = FastAPI(
    title=os.getenv("APP_NAME", "QuestionWork"),
    description="Backend для IT-фриланс биржи с RPG-геймификацией",
    version="0.1.0",
    debug=os.getenv("DEBUG", "False") == "True",
    lifespan=lifespan,
)

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


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    elapsed = time.time() - start
    path = request.url.path
    method = request.method
    status = str(response.status_code)
    try:
        HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(path=path).observe(elapsed)
    except Exception:
        pass
    return response


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

# Настраиваем CORS (разрешаем запросы с фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

# Подключаем роутеры
app.include_router(api_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {"status": "ok", "message": "QuestionWork API is running"}


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
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "False") == "True",
    )
