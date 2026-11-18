"""Decoded recovery boundary algorithm; synthetic fixtures are not runtime proof."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.rehearsal103 import SIGNALS, fresh_record_environments


class FreshnessTest(unittest.TestCase):
    def test_new_delivery_of_old_records_is_not_fresh_and_all_environments_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def write(signal, environment, timestamp):
                plural, scope, leaf = {"traces": ("resourceSpans", "scopeSpans", "spans"),
                    "logs": ("resourceLogs", "scopeLogs", "logRecords"),
                    "metrics": ("resourceMetrics", "scopeMetrics", "metrics")}[signal]
                record = ({"sum": {"dataPoints": [{"timeUnixNano": str(timestamp)}]}} if signal == "metrics"
                    else {"startTimeUnixNano" if signal == "traces" else "timeUnixNano": str(timestamp)})
                directory = root / signal
                directory.mkdir(exist_ok=True)
                path = directory / (environment + ".json")
                path.write_text(json.dumps({plural: [{"resource": {"attributes": [{"key": "deployment.environment.name",
                    "value": {"stringValue": environment}}]}, scope: [{leaf: [record]}]}]}))
                # Newly retried file delivery after boundary, independent of event time.
                os.utime(path, (20, 20))
            for signal in SIGNALS:
                for environment in ("dev", "prod"):
                    write(signal, environment, 9_000_000_000)
            self.assertEqual(fresh_record_environments(root, 10), {signal: set() for signal in SIGNALS})
            for signal in SIGNALS:
                write(signal, "dev", 11_000_000_000)
            self.assertEqual(fresh_record_environments(root, 10), {signal: {"dev"} for signal in SIGNALS})
            for signal in SIGNALS:
                write(signal, "prod", 12_000_000_000)
            self.assertEqual(fresh_record_environments(root, 10), {signal: {"dev", "prod"} for signal in SIGNALS})
            write("logs", "prod", 10_000_000_000)
            self.assertEqual(fresh_record_environments(root, 10)["logs"], {"dev"})
