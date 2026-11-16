"""Focused SDK/lifecycle/privacy contracts; real Collector proof is Linux rehearsal."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.app import create_app
from backend.config import Settings
from backend.database import Database
from backend.telemetry import parent_context
from tools.otel103_receiver import decode, Store, REQUEST_LIMIT


def settings(**values):
    return Settings(JWT_SECRET_KEY="TELEMETRY103_TEST_ONLY_" + "x" * 40,
        DATABASE_URL="sqlite+pysqlite:///:memory:", APP_ENV="test", **values)


class Receipt:
    def __init__(self):
        self.records = {key: [] for key in ("traces", "logs", "metrics")}
        records = self.records
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                signal = self.path.rsplit("/", 1)[-1]
                value, count = decode(signal, self.rfile.read(int(self.headers["Content-Length"])))
                records[signal].append(json.loads(value))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
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
