"""Explicit, app-owned telemetry. Never inspect payloads, SQL or exceptions.

No provider is installed globally. Disabled construction imports no SDK, creates
no workers/sessions/listeners and performs no I/O. The emission API accepts only
fixed enumerations; arbitrary log extras, resources, events and links have no path
to an exporter. See _docs/telemetry103.md for the complete finite schema.
"""
from contextvars import ContextVar
import os
import re
import time

ACTIVE = ContextVar("marketplace_telemetry", default=None)
METHODS = frozenset({"GET", "POST", "PATCH", "DELETE", "PUT", "HEAD", "OPTIONS"})
OPERATIONS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"})
PARENT = re.compile(rb"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})\Z")


def parent_context(headers):
    """Accept one version00 traceparent only. Never extract baggage/tracestate."""
    from opentelemetry.context import Context
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, set_span_in_context
    values = [value for key, value in headers if key == b"traceparent"]
    match = PARENT.fullmatch(values[0]) if len(values) == 1 and len(values[0]) == 55 else None
    if match and int(match[1], 16) and int(match[2], 16):
        return set_span_in_context(NonRecordingSpan(SpanContext(
            int(match[1], 16), int(match[2], 16), True, TraceFlags(int(match[3], 16) & 1))), Context())
    return Context()


def resident_bytes():
    # Actual resident memory, no process command line/host detectors.
    if os.name == "posix":
        with open("/proc/self/statm", "rb") as source:
            return int(source.read(128).split()[1]) * os.sysconf("SC_PAGE_SIZE")
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (key, ctypes.c_size_t) for key in ("peak", "rss", "peak_pool", "pool", "peak_nonpool", "nonpool", "page", "peak_page")]
    values = Counters()
    values.cb = ctypes.sizeof(values)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(values), values.cb)
    return values.rss


class Telemetry:
    def __init__(self, settings, engine, routes):
        self.settings = settings
        self.engine = engine
        def paths(values):
            for route in values:
                if hasattr(route, "path"):
                    yield route.path
                elif hasattr(route, "original_router"):
                    yield from paths(route.original_router.routes)
        self.routes = frozenset(paths(routes))
        self.running = False
        self.listeners = []
        self.health = {"enabled": settings.telemetry_enabled, "started": False}

    def start(self):
        if not self.settings.telemetry_enabled or self.running:
            return
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider, SpanLimits
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk._logs import LoggerProvider, LogRecordLimits
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics import TraceBasedExemplarFilter
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.metrics.view import View
        from opentelemetry.metrics import Observation
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http import Compression
        import requests

        class SafeSession(requests.Session):
            """Supported exporter session hook: no ambient proxy/auth/header capture."""
            def __init__(self):
                super().__init__()
                self.trust_env = False
            def request(self, method, url, **kwargs):
                kwargs.update(headers={"Content-Type": "application/x-protobuf"},
                              timeout=(.2, .5), verify=True, cert=None, allow_redirects=False)
                response = super().request(method, url, **kwargs)
                if response.status_code >= 400:
                    # SDK diagnostics may interpolate response text/reason.
                    response._content = b""
                    response.reason = "Telemetry destination unavailable"
                return response

        class BoundedSpans(BatchSpanProcessor):
            def shutdown(self):
                self._batch_processor.shutdown(timeout_millis=2500)

        class BoundedLogs(BatchLogRecordProcessor):
            def shutdown(self):
                self._batch_processor.shutdown(timeout_millis=2500)

        resource = Resource({"service.name": self.settings.telemetry_service,
            "service.version": self.settings.telemetry_version,
            "deployment.environment.name": self.settings.app_env})
        self.sessions = []
        self.exporters = []
        def exporter(cls, signal):
            session = SafeSession()
            self.sessions.append(session)
            value = cls(endpoint=self.settings.telemetry_endpoint + "/v1/" + signal,
                        headers={}, timeout=1, compression=Compression.NoCompression,
                        session=session, max_request_size=65536)
            self.exporters.append(value)
            return value
        self.traces = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(1)),
            shutdown_on_exit=False, span_limits=SpanLimits(max_attributes=8, max_events=0,
                max_links=0, max_attribute_length=128))
        self.span_processor = BoundedSpans(exporter(OTLPSpanExporter, "traces"),
            max_queue_size=128, max_export_batch_size=32, schedule_delay_millis=1000,
            export_timeout_millis=1000)
        self.traces.add_span_processor(self.span_processor)
        self.logs = LoggerProvider(resource=resource, shutdown_on_exit=False,
            log_record_limits=LogRecordLimits(max_attributes=8, max_attribute_length=128))
        self.log_processor = BoundedLogs(exporter(OTLPLogExporter, "logs"),
            max_queue_size=128, max_export_batch_size=32, schedule_delay_millis=1000,
            export_timeout_millis=1000)
        self.logs.add_log_record_processor(self.log_processor)
        self.reader = PeriodicExportingMetricReader(exporter(OTLPMetricExporter, "metrics"),
            export_interval_millis=1000, export_timeout_millis=1000)
        keys = {"http.route", "http.request.method", "http.response.status_class", "outcome"}
        self.metrics = MeterProvider(resource=resource, metric_readers=[self.reader],
            shutdown_on_exit=False, exemplar_filter=TraceBasedExemplarFilter(),
            views=[View(instrument_name="*", attribute_keys=keys)])
        self.tracer = self.traces.get_tracer("marketplace.safe", "1")
        self.logger = self.logs.get_logger("marketplace.safe", "1")
        meter = self.metrics.get_meter("marketplace.safe", "1")
        self.count = meter.create_counter("http.server.requests", unit="{request}")
        self.duration = meter.create_histogram("http.server.request.duration", unit="s")
        meter.create_observable_counter("process.cpu.time", callbacks=[
            lambda options: [Observation(time.process_time())]], unit="s")
        meter.create_observable_gauge("process.memory.usage", callbacks=[
            lambda options: [Observation(resident_bytes())]], unit="By")
        self.install_database()
        self.running = True
        self.health.update(started=True)

    def install_database(self):
        from sqlalchemy import event
        from opentelemetry.trace import SpanKind, StatusCode
        system = "postgresql" if self.engine.dialect.name == "postgresql" else "sqlite"
        def before(connection, cursor, statement, parameters, context, executemany):
            if ACTIVE.get() is not self or not self.running:
                return
            # Only first SQL keyword is used; no statement/parameter is retained.
            word = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
            operation = word if word in OPERATIONS else "OTHER"
            span = self.tracer.start_span("db.operation", kind=SpanKind.CLIENT,
                attributes={"db.system.name": system, "db.operation.name": operation})
            context._marketplace_telemetry_span = (self, span)
        def finish(context, failed=False):
            pair = getattr(context, "_marketplace_telemetry_span", None)
            if pair is None or pair[0] is not self:
                return
            del context._marketplace_telemetry_span
            pair[1].set_attribute("outcome", "error" if failed else "success")
            if failed:
                pair[1].set_status(StatusCode.ERROR)
            pair[1].end()
        def after(connection, cursor, statement, parameters, context, executemany):
            finish(context)
        def error(context):
            if context.execution_context is not None:
                finish(context.execution_context, True)
        for name, callback in (("before_cursor_execute", before), ("after_cursor_execute", after), ("handle_error", error)):
            event.listen(self.engine, name, callback)
            self.listeners.append((name, callback))

    def emit(self, event="http.request.completed", *, attributes=None, **ignored):
        # Callers cannot inject arbitrary messages, extras, exceptions or attrs.
        if not self.running:
            return
        from opentelemetry._logs import SeverityNumber
        self.logger.emit(body="http.request.completed", event_name="http.request.completed",
                         severity_number=SeverityNumber.INFO)

    def stop(self):
        if not self.running:
            return
        self.running = False
        from sqlalchemy import event
        for name, callback in self.listeners:
            event.remove(self.engine, name, callback)
        self.listeners.clear()
        started = time.monotonic()
        # Each bounded exporter <=1s; queues drain in bounded batches. Shutdown
        # SDK workers with a shared 8s allowance, leaving resource cleanup time.
        self.traces.shutdown()
        self.logs.shutdown()
        self.metrics.shutdown(timeout_millis=max(1, int((8 - (time.monotonic() - started)) * 1000)))
        for session in self.sessions:
            session.close()
        self.health.update(started=False, shutdown_seconds=time.monotonic() - started)


class TelemetryMiddleware:
    def __init__(self, app, telemetry):
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope, receive, send):
        owner = self.telemetry
        if scope["type"] != "http" or not owner.running:
            return await self.app(scope, receive, send)
        from opentelemetry.trace import SpanKind, StatusCode
        method = scope.get("method")
        method = method if method in METHODS else "OTHER"
        started, status = time.monotonic(), 500
        async def safe_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
        token = ACTIVE.set(owner)
        try:
            with owner.tracer.start_as_current_span("http.request", kind=SpanKind.SERVER,
                context=parent_context(scope.get("headers", [])), record_exception=False,
                set_status_on_exception=False) as span:
                try:
                    return await self.app(scope, receive, safe_send)
                finally:
                    route = getattr(scope.get("route"), "path", None)
                    route = route if route in owner.routes else "unmatched"
                    attrs = {"http.route": route, "http.request.method": method,
                        "http.response.status_class": str(status // 100) + "xx" if 100 <= status < 600 else "other",
                        "outcome": "error" if status >= 500 else "success"}
                    span.set_attributes(attrs)
                    if status >= 500:
                        span.set_status(StatusCode.ERROR)
                    owner.count.add(1, attrs)
                    owner.duration.record(time.monotonic() - started, attrs)
                    owner.emit()
        finally:
            ACTIVE.reset(token)
