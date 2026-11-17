"""Focused SDK/lifecycle/privacy contracts; real Collector proof is Linux rehearsal."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.app import create_app
from backend.config import Settings
from backend.database import Database
from backend.telemetry import parent_context, resident_bytes
from tools.otel103_receiver import decode, Store, REQUEST_LIMIT


def settings(**values):
    return Settings(JWT_SECRET_KEY="TELEMETRY103_TEST_ONLY_" + "x" * 40,
        DATABASE_URL="sqlite+pysqlite:///:memory:", APP_ENV="test", **values)


class Receipt:
    def __init__(self):
        self.records = {key: [] for key in ("traces", "logs", "metrics")}
        records = self.records
        self.status, self.response_body, self.location = 200, b"", ""
        receipt = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                signal = self.path.rsplit("/", 1)[-1]
                value, count = decode(signal, self.rfile.read(int(self.headers["Content-Length"])))
                records[signal].append(json.loads(value))
                self.send_response(receipt.status)
                self.send_header("Content-Length", str(len(receipt.response_body)))
                if receipt.location:
                    self.send_header("Location", receipt.location)
                self.end_headers()
                try:
                    self.wfile.write(receipt.response_body)
                except OSError:
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = "http://127.0.0.1:" + str(self.server.server_port)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def spans(self):
        return [span for payload in self.records["traces"] for resource in payload.get("resourceSpans", [])
            for scope in resource.get("scopeSpans", []) for span in scope.get("spans", [])]


def flush(app):
    owner = app.state.telemetry
    owner.traces.force_flush(2000)
    owner.logs.force_flush(2000)
    owner.metrics.force_flush(2000)


class TelemetryTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.receipt = Receipt()
        self.stack.callback(self.receipt.close)

    def app(self, database=None, **values):
        return create_app(settings(TELEMETRY_ENABLED=True, TELEMETRY_ENDPOINT=self.receipt.endpoint, **values), database)

    def account(self, app, client):
        messages = []
        class Sender:
            def send_code(self, recipient, code, purpose):
                messages.append(code)
        app.state.email_sender = Sender()
        email = uuid.uuid4().hex + "@sdu.edu.kz"
        password = "SYNTHETIC_PASSWORD_103_ONLY"
        self.assertEqual(client.post("/auth/register", json={"email": email, "password": password}).status_code, 201)
        self.assertEqual(client.post("/auth/verify-email", json={"email": email, "code": messages[-1]}).status_code, 200)
        response = client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def test_disabled_has_no_sdk_workers_sessions_import_or_connection(self):
        script = """
import sys, threading
from unittest.mock import patch
from backend.app import create_app
from backend.config import Settings
from fastapi.testclient import TestClient
a=create_app(Settings(JWT_SECRET_KEY='x'*48,DATABASE_URL='sqlite+pysqlite:///:memory:'))
with patch('socket.create_connection',side_effect=AssertionError('export forbidden')):
 with TestClient(a) as client:
  assert client.get('/categories').status_code==401
assert 'opentelemetry.sdk' not in sys.modules
assert not any('Otel' in t.name for t in threading.enumerate())
assert not hasattr(a.state.telemetry,'sessions')
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_actual_request_db_log_metrics_parent_and_exemplar_correlation(self):
        app = self.app()
        with TestClient(app) as client:
            headers = self.account(app, client)
            trace, parent = "1234567890abcdef" * 2, "1234567890abcdef"
            headers["traceparent"] = f"00-{trace}-{parent}-01"
            self.assertEqual(client.get("/categories", headers=headers).status_code, 200)
            flush(app)
        spans = self.receipt.spans()
        # Protobuf JSON represents trace/span IDs in base64, compare decoded bytes.
        import base64
        matching = [span for span in spans if base64.b64decode(span["traceId"]).hex() == trace]
        server = next(span for span in matching if span["name"] == "http.request")
        self.assertEqual(base64.b64decode(server["parentSpanId"]).hex(), parent)
        self.assertTrue(any(span["name"] == "db.operation" and span.get("parentSpanId") == server["spanId"] for span in matching))
        logs = [item for payload in self.receipt.records["logs"] for r in payload["resourceLogs"]
            for scope in r["scopeLogs"] for item in scope["logRecords"]]
        self.assertTrue(any(item.get("traceId") == server["traceId"] and item.get("spanId") == server["spanId"] for item in logs))
        names = {metric["name"] for p in self.receipt.records["metrics"] for r in p["resourceMetrics"]
            for scope in r["scopeMetrics"] for metric in scope["metrics"]}
        self.assertTrue({"http.server.requests", "http.server.request.duration", "process.cpu.time", "process.memory.usage"} <= names)
        exemplars = [exemplar for p in self.receipt.records["metrics"] for r in p["resourceMetrics"]
            for scope in r["scopeMetrics"] for metric in scope["metrics"]
            for point in metric.get("histogram", {}).get("dataPoints", []) for exemplar in point.get("exemplars", [])]
        received = {(span["traceId"], span["spanId"]) for span in spans}
        self.assertTrue(any((e.get("traceId"), e.get("spanId")) in received for e in exemplars))

    def test_ambient_config_never_parsed_or_forwarded_and_apps_have_separate_destinations(self):
        canary = "PRIVATE103_" + uuid.uuid4().hex
        environ = {"OTEL_RESOURCE_ATTRIBUTES": "private=" + canary, "OTEL_SERVICE_NAME": canary,
            "OTEL_EXPORTER_OTLP_HEADERS": canary, "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:1",
            "OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE": canary, "OTEL_EXPORTER_OTLP_CLIENT_KEY": canary,
            "HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1"}
        for signal in ("TRACES", "LOGS", "METRICS"):
            for key in ("HEADERS", "CLIENT_CERTIFICATE", "CLIENT_KEY", "CERTIFICATE"):
                environ["OTEL_EXPORTER_OTLP_" + signal + "_" + key] = canary
            environ["OTEL_EXPORTER_OTLP_" + signal + "_ENDPOINT"] = "http://127.0.0.1:1"
            environ["OTEL_PYTHON_EXPORTER_OTLP_HTTP_" + signal + "_CREDENTIAL_PROVIDER"] = canary
        other = Receipt()
        self.stack.callback(other.close)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.addHandler(handler)
        try:
            # The replaced HTTP package is no longer a runtime dependency. A
            # poison module preserves the original Session.send interception:
            # neither importing nor invoking an ambient Requests path is needed.
            poisoned_requests = Mock()
            poisoned_requests.Session.send.side_effect = AssertionError("ambient transport forbidden")
            with patch.dict(os.environ, environ), patch.dict(sys.modules, {"requests": poisoned_requests}):
                one = self.app()
                two = create_app(settings(TELEMETRY_ENABLED=True, TELEMETRY_ENDPOINT=other.endpoint, TELEMETRY_VERSION="2"))
                with TestClient(two) as c2:
                    with TestClient(one) as c1:
                        self.assertEqual(c1.get("/categories").status_code, 401)
                        self.assertEqual(c2.get("/categories").status_code, 401)
                        flush(one)
                        flush(two)
                    before = len(other.spans())
                    self.assertEqual(c2.get("/auth/me").status_code, 401)
                    flush(two)
                    self.assertGreater(len(other.spans()), before)
                poisoned_requests.Session.send.assert_not_called()
                poisoned_requests.Session.assert_not_called()
                self.assertEqual(os.environ["OTEL_EXPORTER_OTLP_HEADERS"], canary)
            self.assertNotIn(canary, stream.getvalue())
            self.assertNotIn(canary, json.dumps([self.receipt.records, other.records]))
            self.assertTrue(all(self.receipt.records[signal] and other.records[signal] for signal in ("traces", "logs", "metrics")))
        finally:
            root.removeHandler(handler)
        self.assertEqual(root.handlers, original_handlers)

    def test_actual_resident_memory_periodic_shutdown_and_safe_native_failure(self):
        for _ in range(20):
            self.assertGreater(resident_bytes(), 1024 * 1024)
            self.assertLess(resident_bytes(), 128 * 1024 ** 3)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger().addHandler(handler)
        self.stack.callback(logging.getLogger().removeHandler, handler)
        app = self.app()
        with TestClient(app) as client:
            self.assertEqual(client.get("/categories").status_code, 401)
            time.sleep(1.2)
            flush(app)
            self.assertEqual(app.state.telemetry.health["memory_collection"], "available")
            with patch("backend.telemetry.resident_bytes", side_effect=OSError("PRIVATE_NATIVE_103")):
                flush(app)
                self.assertEqual(app.state.telemetry.snapshot()["memory_collection"], "unavailable")
                self.assertEqual(client.get("/auth/me").status_code, 401)
        points = [p for document in self.receipt.records["metrics"] for r in document["resourceMetrics"]
            for scope in r["scopeMetrics"] for metric in scope["metrics"] if metric["name"] == "process.memory.usage"
            for p in metric["gauge"]["dataPoints"]]
        self.assertTrue(points)
        self.assertTrue(all(float(p.get("asInt", p.get("asDouble", 0))) > 0 for p in points))
        self.assertNotIn("PRIVATE_NATIVE_103", stream.getvalue())
        self.assertNotIn("Traceback", stream.getvalue())

    def test_actual_redirect_failure_and_oversize_response_are_safe_and_recover(self):
        other = Receipt()
        self.stack.callback(other.close)
        canary = "PRIVATE_RESPONSE_103_" + uuid.uuid4().hex
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger().addHandler(handler)
        self.stack.callback(logging.getLogger().removeHandler, handler)
        app = self.app()
        with TestClient(app) as client:
            for status, payload in ((302, canary.encode()), (503, canary.encode()), (200, b"x" * 4097)):
                self.receipt.status = status
                self.receipt.response_body = payload
                self.receipt.location = other.endpoint
                self.assertEqual(client.get("/categories").status_code, 401)
                flush(app)
            snapshot = app.state.telemetry.snapshot()
            self.assertTrue(all(item["records_failed"] > 0 for item in snapshot["exports"].values()))
            self.assertFalse(any(other.records.values()))
            self.receipt.status, self.receipt.response_body = 200, b""
            self.assertEqual(client.get("/auth/me").status_code, 401)
            flush(app)
            self.assertTrue(all(item["records_accepted"] > 0 for item in app.state.telemetry.snapshot()["exports"].values()))
        self.assertNotIn(canary, stream.getvalue())
        self.assertNotIn("Traceback", stream.getvalue())

    def test_private_canaries_absent_from_all_decoded_signals(self):
        canary = "PRIVATE103_" + uuid.uuid4().hex
        app = self.app()
        @app.get("/test-private")
        def private():
            app.state.telemetry.emit(canary, attributes={"private": canary}, exception=ValueError(canary))
            with app.state.database.session() as session:
                session.execute(text("SELECT :value"), {"value": canary})
            return {"safe": True}
        @app.get("/test-failure")
        def failure():
            with app.state.database.session() as session:
                session.execute(text("SELECT " + canary))
        with TestClient(app, raise_server_exceptions=False) as client:
            self.assertEqual(client.get("/test-private?private=" + canary, headers={"Cookie": canary, "baggage": "private=" + canary, "tracestate": canary}).status_code, 200)
            self.assertEqual(client.get("/" + canary).status_code, 404)
            self.assertEqual(client.post("/auth/login", json={"email": canary, "password": canary}).status_code, 422)
            self.assertEqual(client.get("/test-failure").status_code, 500)
            flush(app)
        raw = json.dumps(self.receipt.records)
        self.assertNotIn(canary, raw)
        for span in self.receipt.spans():
            self.assertFalse(span.get("events"))
            self.assertFalse(span.get("links"))

    def test_borrowed_shared_engine_multiple_apps_concurrent_context_and_restart(self):
        database = Database(settings())
        self.stack.callback(database.dispose)
        app1, app2 = self.app(database), self.app(database)
        with TestClient(app1) as one, TestClient(app2) as two:
            def fetch(pair):
                client, digit = pair
                return client.get("/auth/me", headers={"traceparent": "00-" + digit * 32 + "-" + digit * 16 + "-01"}).status_code
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(value == 401 for value in pool.map(fetch, [(one, "1"), (two, "2")] * 8)))
            self.assertEqual(len(app1.state.telemetry.listeners), 3)
            flush(app1)
            flush(app2)
        self.assertEqual(app1.state.telemetry.listeners, [])
        self.assertEqual(app2.state.telemetry.listeners, [])
        self.assertTrue(database.check_connection())
        with TestClient(app1) as client:
            self.assertEqual(client.get("/categories").status_code, 401)
        self.assertLess(app1.state.telemetry.health["shutdown_seconds"], 10)

    def test_absent_collector_requests_startup_and_shutdown_bounded(self):
        app = create_app(settings(TELEMETRY_ENABLED=True, TELEMETRY_ENDPOINT="http://127.0.0.1:1"))
        begin = time.monotonic()
        with TestClient(app) as client:
            self.assertEqual(client.get("/categories").status_code, 401)
        self.assertLess(time.monotonic() - begin, 10)

    def test_propagation_rejects_invalid_oversized_duplicate_and_zero_ids(self):
        from opentelemetry.trace import get_current_span
        good = b"00-" + b"1" * 32 + b"-" + b"2" * 16 + b"-01"
        self.assertTrue(get_current_span(parent_context([(b"traceparent", good)])).get_span_context().is_valid)
        for headers in ([(b"traceparent", good * 100)], [(b"traceparent", good)] * 2,
            [(b"traceparent", good.replace(b"1", b"0"))], [(b"traceparent", b"ff" + good[2:])]):
            self.assertFalse(get_current_span(parent_context(headers)).get_span_context().is_valid)

    def test_receiver_rejects_oversized_and_bounds_private_storage(self):
        with self.assertRaises(ValueError):
            decode("traces", b"x" * (REQUEST_LIMIT + 1))
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory, limit=50)
            for i in range(10):
                self.assertTrue(store.append(b"x" * 30, 1))
            self.assertLessEqual(sum(p.stat().st_size for p in Path(directory).iterdir()), 50)
            self.assertEqual(store.evicted, 9)
            self.assertFalse(store.append(b"x" * 51, 1))

    def test_endpoint_and_resource_config_reject_arbitrary_identity(self):
        for value in ("person@example.invalid", "host-secret-name", "a" * 100):
            with self.assertRaises(ValueError):
                settings(TELEMETRY_VERSION=value)
        for value in ("http://external.example", "http://user:password@localhost", "http://localhost/path?secret=value"):
            with self.assertRaises(ValueError):
                settings(TELEMETRY_ENDPOINT=value)
