"""Safety contracts for the opt-in controller; actual Linux evidence is separate."""
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools.rehearsal101 import Failure
from tools.rehearsal103 import BudgetLedger, PLANS, attribute_map, decoded, identity, validate_http_attributes
from tools.otel103_receiver import make_server


class RehearsalSafetyTest(unittest.TestCase):
    def test_nested_budget_charges_supporting_work_once_and_rejects_overrun(self):
        clock = [0]
        ledger = BudgetLedger("capacity", lambda: clock[0])
        with ledger.stage("measurement"):
            clock[0] += 5
            with ledger.stage("transitions"):
                clock[0] += 7
            clock[0] += 3
        self.assertEqual(ledger.elapsed["measurement"], 8)
        self.assertEqual(ledger.elapsed["transitions"], 7)
        with self.assertRaises(Failure):
            with ledger.stage("measurement"):
                clock[0] += ledger.limits["measurement"]
        self.assertEqual(sum(ledger.limits.values()) + 120 + 90 + 60 + 10, 1800)

    def test_controller_deadline_failure_still_cleans_and_writes_only_failure_summary(self):
        import tools.rehearsal103 as module
        class Controller:
            def __init__(self, part):
                self.record = {"result": "FAIL", "cleanup": False}
            def main(self):
                raise Failure("budget-measurement")
            def cleanup(self):
                self.record["cleanup"] = True
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "ROOT", Path(directory)), \
            patch.object(module, "Controller", Controller), patch.object(module.sys, "platform", "linux"), \
            patch.object(module.sys, "argv", ["rehearsal103", "--confirm-disposable", "issue-103-synthetic-only"]):
            self.assertEqual(module.main(), 1)
            value = json.loads((Path(directory) / "rehearsal103-safe/summary.json").read_text())
            self.assertTrue(value["cleanup"])
            self.assertEqual(value["result"], "FAIL")
            self.assertEqual(value["failure_stage"], "budget-measurement")

    def test_http_privacy_audit_rejects_raw_paths_identity_fields_and_unbounded_values(self):
        values = {"http.route": "/listings/{listing_id}", "http.request.method": "GET",
            "http.response.status_class": "2xx", "outcome": "success"}
        validate_http_attributes(values, {"/listings/{listing_id}", "unmatched"})
        for changed in ({"http.route": "/listings/123"}, {"http.request.method": "PRIVATE_103"},
            {"http.response.status_class": "PRIVATE_103"}, {"outcome": "PRIVATE_103"}, {"user.id": "123"}):
            with self.assertRaises(Failure):
                validate_http_attributes({**values, **changed}, {"/listings/{listing_id}", "unmatched"})
        with self.assertRaises(Failure):
            attribute_map([{"key": "outcome", "value": {"stringValue": "success"}}] * 2)

    def test_trace_and_log_retry_identity_does_not_count_deliveries_as_unique(self):
        trace = {"traceId": "synthetic-trace", "spanId": "synthetic-span", "name": "http.request"}
        self.assertEqual(identity("traces", {}, trace), identity("traces", {}, {**trace, "attributes": []}))
        log = {"traceId": "synthetic-trace", "spanId": "synthetic-span", "timeUnixNano": "1", "body": {"stringValue": "http.request.completed"}}
        self.assertEqual(len({identity("logs", {}, log), identity("logs", {}, dict(log))}), 1)

    def test_decoded_storage_reader_rejects_oversize_files_before_json_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "traces").mkdir()
            (root / "traces/oversize.json").write_bytes(b"x" * 524289)
            with self.assertRaises(Failure):
                list(decoded(root, "traces"))

    def test_receiver_actual_http_rejects_oversize_compression_and_private_parser_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            server = make_server("traces", directory, 0, "127.0.0.1")
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                for headers, body in (({"Content-Type": "application/x-protobuf"}, b"x" * 65537),
                    ({"Content-Type": "application/x-protobuf", "Content-Encoding": "gzip"}, b"PRIVATE103_INVALID_PROTO")):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    connection.request("POST", "/v1/traces", body, headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 400)
                    self.assertNotIn(b"PRIVATE103", response.read())
                    connection.close()
                with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
                    connection.sendall(b"PRIVATE103_BAD REQUEST SYNTAX EXTRA\r\n\r\n")
                    self.assertNotIn(b"PRIVATE103", connection.recv(4096))
                self.assertEqual(list(Path(directory).glob("*.json")), [])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(3)

    def test_split_plan_preserves_same_host_capacity_and_all_destination_failure_scope(self):
        capacity, functional = PLANS["capacity"], PLANS["functional"]
        self.assertGreaterEqual(capacity["paired_runs"], 3)
        self.assertGreaterEqual(capacity["paired_phase_seconds"], 120)
        self.assertGreaterEqual(capacity["enabled_load_seconds"], 300)
        self.assertEqual(set(functional["outages"]), {"collector", "traces", "logs", "metrics", "prometheus"})
        for plan in (capacity, functional):
            self.assertGreaterEqual(plan["outage_seconds"], 60)
            self.assertLessEqual(plan["recovery_max_seconds"], 120)
        self.assertFalse(PLANS["preflight"]["capacity_acceptance"])

    def test_missing_disposable_confirmation_refuses_before_any_runtime_setup(self):
        result = subprocess.run([sys.executable, "-m", "tools.rehearsal103", "--part", "preflight"],
            capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"--confirm-disposable", result.stderr)
