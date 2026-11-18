"""Fixture-only safe SDK observations, separate from supported app/readiness.

Runs the identical packaged app source in both modes. Observes actual processor
admission/queue drops; never substitutes records/exporters or bypasses auth.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import threading

from backend.packaged import create_packaged_app


def create_app():
    app = create_packaged_app()
    owner = app.api.state.telemetry
    counts = {signal: {"emitted": 0, "unsampled_on_end": 0, "queue_dropped": 0,
        "other_dropped": 0, "submitted_to_exporter": 0, "queue_peak_observed": 0} for signal in ("traces", "logs")}
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            value = owner.snapshot()
            with lock:
                value["processor_observations"] = {key: dict(item) for key, item in counts.items()}
            value["sdk_imported"] = "opentelemetry.sdk" in sys.modules
            value["sdk_worker_threads"] = sum(thread.name.startswith(("OtelBatch", "OtelPeriodic")) for thread in threading.enumerate())
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = HTTPServer(("0.0.0.0", 8989), Handler)
    server.timeout = 1
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
    worker.start()

    def observe(processor, signal, method):
        original_metrics = processor._batch_processor._metrics
        class ObservedMetrics:
            def __getattr__(self, name):
                return getattr(original_metrics, name)
            def drop_items(self, count, error_type="queue_full"):
                with lock:
                    counts[signal]["queue_dropped" if error_type == "queue_full" else "other_dropped"] += count
                return original_metrics.drop_items(count, error_type)
            def finish_items(self, count):
                with lock:
                    counts[signal]["submitted_to_exporter"] += count
                return original_metrics.finish_items(count)
        processor._batch_processor._metrics = ObservedMetrics()
        original = getattr(processor, method)
        def emit(value):
            if signal == "traces" and not value.context.trace_flags.sampled:
                with lock:
                    counts[signal]["unsampled_on_end"] += 1
                return original(value)
            queue = processor._batch_processor._queue
            with lock:
                counts[signal]["emitted"] += 1
                counts[signal]["queue_peak_observed"] = max(counts[signal]["queue_peak_observed"], len(queue))
            return original(value)
        setattr(processor, method, emit)

    class Fixture:
        async def __call__(self, scope, receive, send):
            async def observed(message):
                if message["type"] == "lifespan.startup.complete" and owner.running:
                    observe(owner.span_processor, "traces", "on_end")
                    observe(owner.log_processor, "logs", "on_emit")
                    # Dedicated unmeasured privacy probe: real isolated PG work,
                    # no account/role seed and no route/auth bypass. Normal HTTP
                    # journeys/read workload remain the supported real app.
                    from backend.telemetry import ACTIVE
                    from opentelemetry.trace import StatusCode
                    from sqlalchemy import text
                    canaries = json.loads(Path("/canary-probe.json").read_text())
                    token = ACTIVE.set(owner)
                    try:
                        with owner.tracer.start_as_current_span("db.operation", attributes={
                            "db.system.name": "postgresql", "db.operation.name": "SELECT"},
                            record_exception=False, set_status_on_exception=False) as span:
                            try:
                                with owner.tracer.start_as_current_span("db.operation", attributes={
                                    "db.system.name": "postgresql", "db.operation.name": "SELECT"},
                                    record_exception=False, set_status_on_exception=False) as dependency:
                                    try:
                                        with app.api.state.database.session() as session:
                                            session.execute(text("SELECT :private"), {"private": canaries[0]})
                                            session.execute(text("SELECT 1/0"))
                                    except Exception:
                                        dependency.set_status(StatusCode.ERROR)
                                        dependency.set_attribute("outcome", "error")
                                        # Actual failed PG work with a private
                                        # dependency wrapper exception crossing
                                        # SDK scope; native PG error is generic.
                                        raise RuntimeError(canaries[1]) from None
                            except Exception as error:
                                span.set_status(StatusCode.ERROR)
                                span.set_attribute("outcome", "error")
                                owner.emit(canaries[2], attributes={"private": canaries[3]}, exception=error)
                    finally:
                        ACTIVE.reset(token)
                await send(message)
            try:
                return await app(scope, receive, observed if scope["type"] == "lifespan" else send)
            finally:
                if scope["type"] == "lifespan":
                    value = {"enabled": owner.settings.telemetry_enabled, "health": owner.snapshot(),
                        "processor_observations": counts}
                    if hasattr(owner, "exporters"):
                        value["exports"] = {signal: dict(exporter.transport.counters)
                            for signal, exporter in zip(("traces", "logs", "metrics"), owner.exporters)}
                        value["queued_on_shutdown"] = {signal: len(processor._batch_processor._queue)
                            for signal, processor in (("traces", owner.span_processor), ("logs", owner.log_processor))}
                        value["sdk_workers_alive_after_shutdown"] = sum(processor._batch_processor._worker_thread.is_alive()
                            for processor in (owner.span_processor, owner.log_processor)) + int(owner.reader._daemon_thread.is_alive())
                    print("TELEMETRY103_SHUTDOWN " + json.dumps(value), flush=True)
                    server.shutdown()
                    server.server_close()
                    worker.join(1)
    return Fixture()
