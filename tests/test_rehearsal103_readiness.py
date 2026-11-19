"""Handler readiness and offered-clock boundaries, not actual runtime evidence."""
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

from tools.rehearsal101 import Failure
from tools.rehearsal103 import BudgetLedger, Controller
from tools.rehearsal103_readiness import wait_for_receivers


class ImmediatePool:
    def __init__(self, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def submit(self, function, *args):
        value = Future()
        value.set_result(function(*args))
        return value
    def shutdown(self, **kwargs):
        pass


class ReadinessTest(unittest.TestCase):
    def test_transient_resets_retry_actual_probe_and_permanent_failure_hits_shared_deadline(self):
        clock, attempts, diagnostics = [0.0], {}, {}
        def sleep(seconds):
            clock[0] += seconds
        def probe(role, deadline):
            self.assertLessEqual(deadline, 1)
            attempts[role] = attempts.get(role, 0) + 1
            if attempts[role] == 1:
                raise ConnectionResetError("PRIVATE_ERROR_MUST_NOT_APPEAR")
        wait_for_receivers(probe, diagnostics, deadline=1, clock=lambda: clock[0], sleep=sleep)
        self.assertTrue(all(value["ready"] for value in diagnostics.values()))
        self.assertTrue(all(len(value["attempts"]) == 2 for value in diagnostics.values()))
        self.assertNotIn("PRIVATE_ERROR", json.dumps(diagnostics))
        self.assertEqual(diagnostics["traces"]["attempts"][0]["failure_class"], "connection-reset")
        def never(role, deadline):
            raise ConnectionRefusedError("PRIVATE_NATIVE_PATH")
        clock[0] = 0
        with self.assertRaisesRegex(Failure, "receiver-startup-traces"):
            wait_for_receivers(never, {}, deadline=1, clock=lambda: clock[0], sleep=sleep)
        self.assertLessEqual(clock[0], 1)

    def test_real_listener_not_ready_until_handler_health_succeeds(self):
        ready = threading.Event()
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                calls.append(self.path)
                if not ready.is_set():
                    ready.set()
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                body = b'{"ready":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = HTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        diagnostics = {}
        def probe(role, deadline):
            status, _, body = Controller.drain_request("http://127.0.0.1:" + str(server.server_port), "/health", deadline)
            self.assertEqual((status, json.loads(body)), (200, {"ready": True}))
        try:
            wait_for_receivers(probe, diagnostics, deadline=time.monotonic() + 3)
            self.assertGreaterEqual(len(diagnostics["traces"]["attempts"]), 2)
            self.assertTrue(all(value["ready"] for value in diagnostics.values()))
            self.assertTrue(all(path == "/health" for path in calls))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)
            self.assertFalse(worker.is_alive())

    def test_initial_metadata_is_ledger_charged_before_offered_64rps_clock_and_stopped_is_unknown(self):
        for stopped in (None, "collector"):
            clock, offers = [0.0], []
            controller = object.__new__(Controller)
            controller.record = {"phases": {}, "samples": []}
            controller.ledger = BudgetLedger("functional", lambda: clock[0])
            controller.stacks = [{"name": "dev"}, {"name": "prod"}]
            controller.obs = {"directory": "unused"}
            controller.deadline = 100
            controller.sampler = Mock()
            controller.sampler_cancel = threading.Event()
            controller.failed_sampler_join_seconds = 0
            controller.refresh_if_needed = Mock()
            def collector():
                clock[0] += 1
                return {}
            controller.collector_metrics = Mock(side_effect=collector)
            def read(stack):
                offers.append((stack["name"], clock[0]))
                return True, .01
            controller.read = read
            def sleep(seconds):
                clock[0] += seconds
            with patch("tools.rehearsal103.time.monotonic", side_effect=lambda: clock[0]), \
                patch("tools.rehearsal103.time.sleep", side_effect=sleep), \
                patch("tools.rehearsal103.ThreadPoolExecutor", ImmediatePool), \
                patch("tools.rehearsal103.stored_counts", return_value={}), \
                patch("tools.rehearsal103_sampling.SnapshotPump"):
                result = controller.phase("sdk-backpressure-collector-paused", .2, rate=64, stopped=stopped)
            self.assertEqual(result["target_requests_per_second_per_environment"], 64)
            self.assertEqual(result["concurrency_per_environment"], 4)
            self.assertEqual(len(offers), 26)
            if stopped:
                controller.collector_metrics.assert_not_called()
                self.assertIsNone(result["collector_before"])
                self.assertIsNone(result["collector_after"])
            else:
                self.assertEqual(offers[0][1], 1)
                self.assertGreaterEqual(controller.ledger.elapsed["measurement"], result["duration_seconds"] + 2)
                self.assertEqual(result["entry_metadata_seconds"], 1)
