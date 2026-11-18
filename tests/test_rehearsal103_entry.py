"""Real absolute-entry packaging and SDK wire contract; Collector proof is separate."""
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest


class ReceiverEntryTest(unittest.TestCase):
    def test_absolute_entry_without_pythonpath_receives_each_actual_sdk_signal(self):
        from backend.otel_export import exporters
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        root = Path(__file__).resolve().parents[1]
        resource = Resource({"service.name": "student-marketplace", "service.version": "0.1.0",
            "deployment.environment.name": "test"})
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            app, unrelated = base / "app", base / "unrelated"
            (app / "backend").mkdir(parents=True)
            unrelated.mkdir()
            shutil.copyfile(root / "tools/otel103_receiver.py", app / "receiver103.py")
            for name in ("__init__.py", "otel_export.py"):
                shutil.copyfile(root / "backend" / name, app / "backend" / name)
            for index, signal in enumerate(("traces", "logs", "metrics")):
                with self.subTest(signal=signal):
                    with socket.socket() as reservation:
                        reservation.bind(("127.0.0.1", 0))
                        number = reservation.getsockname()[1]
                    directory = base / signal
                    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "LANG") if key in os.environ}
                    child = subprocess.Popen([sys.executable, "-E", str(app / "receiver103.py"),
                        "--signal", signal, "--private-directory", str(directory), "--host", "127.0.0.1",
                        "--port", str(number)], cwd=unrelated, env=environment,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    def health():
                        connection = http.client.HTTPConnection("127.0.0.1", number, timeout=.3)
                        try:
                            connection.request("GET", "/health")
                            response = connection.getresponse()
                            self.assertEqual(response.status, 200)
                            return json.loads(response.read(4096))
                        finally:
                            connection.close()
                    try:
                        deadline = time.monotonic() + 8
                        while True:
                            try:
                                health()
                                break
                            except OSError:
                                if child.poll() is not None or time.monotonic() >= deadline:
                                    self.fail("isolated receiver health unavailable")
                                time.sleep(.03)
                        selected = exporters("http://127.0.0.1:" + str(number))[index]
                        if signal == "traces":
                            provider = TracerProvider(resource=resource, shutdown_on_exit=False)
                            provider.add_span_processor(SimpleSpanProcessor(selected))
                            with provider.get_tracer("student-marketplace.telemetry").start_as_current_span("http.request"):
                                pass
                        elif signal == "logs":
                            provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
                            provider.add_log_record_processor(SimpleLogRecordProcessor(selected))
                            provider.get_logger("student-marketplace.telemetry").emit(body="request.complete", severity_number=9)
                        else:
                            reader = PeriodicExportingMetricReader(selected, export_interval_millis=60000)
                            provider = MeterProvider(resource=resource, metric_readers=[reader], shutdown_on_exit=False)
                            provider.get_meter("student-marketplace.telemetry").create_counter("http.server.requests").add(1)
                        try:
                            self.assertTrue(provider.force_flush(2000))
                            self.assertGreater(health()["accepted"], 0)
                            documents = list(directory.glob("*.json"))
                            self.assertTrue(documents)
                            key = {"traces": "resourceSpans", "logs": "resourceLogs", "metrics": "resourceMetrics"}[signal]
                            self.assertTrue(any(json.loads(path.read_text()).get(key) for path in documents))
                        finally:
                            provider.shutdown()
                    finally:
                        child.terminate()
                        output, errors = child.communicate(timeout=5)
                        self.assertEqual(errors, b"")
                        self.assertEqual(output, b"")
