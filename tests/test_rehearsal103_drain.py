"""Quiescence/deadline algorithms and real bounded read; not Collector evidence."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import unittest
from unittest.mock import patch

from tools.rehearsal101 import Failure
from tools.rehearsal103 import Controller
from tools.rehearsal103_drain import COMPONENTS, SIGNALS, wait_for_drain


def snapshot():
    return {"queues": {name: {"capacity": 2, "size": 0} for name in COMPONENTS},
        "collector_counters": {"accepted": 10, "sent": 10}, "receiver_counters": {signal: {
            "accepted": 10, "refused_requests": 0, "refused_records": 0,
            "unknown_refused_requests": 0, "evicted_files": 0} for signal in SIGNALS}}


class DrainTest(unittest.TestCase):
    def run_clock(self, change, maximum=12):
        clock = [0.0]
        def observe(deadline):
            self.assertLess(clock[0], deadline)
            value = snapshot()
            change(value, clock[0])
            clock[0] += .05
            return value
        def sleep(seconds):
            clock[0] += seconds
        return wait_for_drain(observe, clock=lambda: clock[0], sleep=sleep, maximum=maximum)

    def test_empty_queue_alone_never_passes_before_retry_and_read_boundary(self):
        result = self.run_clock(lambda value, now: None)
        self.assertGreaterEqual(result["actual_seconds"], 8)
        self.assertLess(result["actual_seconds"], 12)
        self.assertGreaterEqual(result["stable_counter_window_seconds"], 8)
        self.assertTrue(all(set(row["receiver_counters"]) == set(SIGNALS) for row in result["polls"]))

    def test_late_delivery_restarts_stable_window_and_nonempty_queue_cannot_pass(self):
        def late(value, now):
            if now >= 2:
                value["receiver_counters"]["traces"]["accepted"] = 11
        self.assertGreaterEqual(self.run_clock(late)["actual_seconds"], 10)
        def too_late(value, now):
            if now >= 5:
                value["receiver_counters"]["traces"]["accepted"] = 11
        with self.assertRaisesRegex(Failure, "post-stop-drain-deadline"):
            self.run_clock(too_late)
        with self.assertRaisesRegex(Failure, "post-stop-drain-deadline"):
            self.run_clock(lambda value, now: value["queues"][COMPONENTS[0]].update(size=1))

    def test_missing_refused_evicted_or_reset_observations_fail_without_zero_fallback(self):
        for change in (lambda v, t: v["queues"].pop(COMPONENTS[0]),
            lambda v, t: v["receiver_counters"]["logs"].update(refused_requests=1),
            lambda v, t: v["receiver_counters"]["metrics"].update(evicted_files=1),
            lambda v, t: v["collector_counters"].clear(),
            lambda v, t: v["receiver_counters"]["traces"].update(accepted=9 if t > 1 else 10)):
            with self.assertRaises(Failure):
                self.run_clock(change)

    def test_late_observation_fails_and_keeps_prior_actual_poll_evidence(self):
        clock, polls = [0.0], []
        def observe(deadline):
            clock[0] += 13
            return snapshot()
        with self.assertRaisesRegex(Failure, "drain-observation-deadline"):
            wait_for_drain(observe, clock=lambda: clock[0], sleep=lambda seconds: None, polls=polls)
        self.assertEqual(polls, [])

    def test_real_response_body_read_uses_shared_absolute_deadline_and_closes_connection(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                if self.path == "/metrics":
                    self.wfile.write(b"ok")
                    return
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(.6)
        server = HTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            status, _, body = Controller.drain_request("http://127.0.0.1:" + str(server.server_port),
                "/metrics", time.monotonic() + 1)
            self.assertEqual((status, body), (200, b"ok"))
            began = time.monotonic()
            with self.assertRaises(TimeoutError):
                Controller.drain_request("http://127.0.0.1:" + str(server.server_port), "/health", began + .15)
            self.assertLess(time.monotonic() - began, .5)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)
            self.assertFalse(worker.is_alive())

    def test_drain_refuses_before_observation_unless_both_sdk_workers_stopped(self):
        controller = object.__new__(Controller)
        for values in ([], [{"environment": "dev", "sdk_workers_alive_after_shutdown": 0}],
            [{"environment": "dev", "sdk_workers_alive_after_shutdown": 0},
                {"environment": "prod", "sdk_workers_alive_after_shutdown": 1}]):
            controller.record = {"app_shutdowns": values}
            with self.assertRaisesRegex(Failure, "all-sdk-producers-stopped-before-drain"):
                controller.drain_after_shutdown()

    def test_controller_observes_only_collector_and_receivers_after_both_stops(self):
        controller = object.__new__(Controller)
        controller.record = {"app_shutdowns": [{"environment": env, "sdk_workers_alive_after_shutdown": 0}
            for env in ("dev", "prod")]}
        controller.deadline = time.monotonic() + 30
        controller.obs = {"endpoints": {signal: "http://127.0.0.1:" + str(12000 + index)
            for index, signal in enumerate(SIGNALS)}}
        actual = {}
        for component in COMPONENTS:
            actual["otelcol_exporter_queue_capacity|" + component] = 2
            actual["otelcol_exporter_queue_size|" + component] = 0
            unit = "spans" if component.endswith("traces") else "log_records" if component.endswith("logs") else "metric_points"
            for prefix in ("sent_", "send_failed_"):
                actual["otelcol_exporter_" + prefix + unit + "_total|" + component] = 10
        for unit in ("spans", "log_records", "metric_points"):
            for prefix in ("accepted_", "refused_"):
                actual["otelcol_receiver_" + prefix + unit + "_total"] = 10
        observed = []
        def get(origin, path, deadline):
            observed.append((origin, path))
            self.assertGreater(deadline, time.monotonic())
            import json
            return 200, {}, json.dumps(snapshot()["receiver_counters"]["traces"]).encode()
        def drain(observe, **kwargs):
            value = observe(time.monotonic() + 1)
            self.assertEqual(set(value["queues"]), set(COMPONENTS))
            return {"actual_seconds": .01}
        with patch.object(Controller, "api", side_effect=AssertionError("application call during drain")), \
            patch.object(Controller, "read", side_effect=AssertionError("application read during drain")), \
            patch.object(Controller, "collector_metrics", return_value=actual), \
            patch.object(Controller, "drain_request", side_effect=get), \
            patch("tools.rehearsal103_drain.wait_for_drain", side_effect=drain):
            controller.drain_after_shutdown()
        self.assertEqual(observed, [(controller.obs["endpoints"][signal], "/health") for signal in SIGNALS])
        self.assertEqual(controller.record["post_stop_drain"]["result"], "PASS")
