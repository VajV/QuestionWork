from contextlib import contextmanager

try:
    from opentelemetry import trace, context as otel_context
    from opentelemetry.trace import get_current_span
    _tracer = trace.get_tracer(__name__)
    _OTEL_AVAILABLE = True
except Exception:
    _tracer = None
    _OTEL_AVAILABLE = False


def propagate_request_id(request_id: str | None) -> None:
    """Set X-Request-ID as an attribute on the current OTEL span (L-07)."""
    if not _OTEL_AVAILABLE or not request_id:
        return
    try:
        span = get_current_span()
        if span and span.is_recording():
            span.set_attribute("http.request_id", request_id)
    except Exception:
        pass


@contextmanager
def db_span(name: str, query: str | None = None, params: object | None = None):
    """Context manager for a database-related OTEL span.

    Safe no-op when OpenTelemetry is not installed/initialized.
    Sets `db.operation` (name only, never raw SQL) and `db.param_count` attributes when available.
    """
    if _OTEL_AVAILABLE and _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            try:
                if query:
                    # P2-05: Never send raw SQL to traces — only the span name identifies the operation
                    span.set_attribute("db.operation", name)
                if params is not None:
                    span.set_attribute("db.param_count", len(params) if hasattr(params, "__len__") else 1)
            except Exception:
                # Guard against any attribute-setting errors
                pass
            yield span
    else:
        # simple noop context manager
        yield None
