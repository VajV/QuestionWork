from contextlib import contextmanager

try:
    from opentelemetry import trace
    _tracer = trace.get_tracer(__name__)
    _OTEL_AVAILABLE = True
except Exception:
    _tracer = None
    _OTEL_AVAILABLE = False


@contextmanager
def db_span(name: str, query: str | None = None, params: object | None = None):
    """Context manager for a database-related OTEL span.

    Safe no-op when OpenTelemetry is not installed/initialized.
    Sets `db.statement` and `db.params` attributes when available.
    """
    if _OTEL_AVAILABLE and _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            try:
                if query:
                    span.set_attribute("db.statement", query)
                if params is not None:
                    span.set_attribute("db.params", str(params))
            except Exception:
                # Guard against any attribute-setting errors
                pass
            yield span
    else:
        # simple noop context manager
        yield None
