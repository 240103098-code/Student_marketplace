"""Synthetic algorithm fixtures only; these are not Linux runtime evidence."""
import copy
import unittest

from tools.rehearsal101 import Failure
from tools.rehearsal103_report import build_report, resource_groups


def fixture():
    record = {"part": "capacity", "source": "a" * 40, "application_image_id": "unit-only",
        "phase_host_fingerprint": "unit-only", "samples": [], "phases": {},
        "outages": {"collector": {"seconds": 60}}, "recoveries": {"collector": {"fresh_three_signal_seconds": 7}},
        "expanded_image_bytes_by_role": {"unit-only": 1000},
        "docker_disk_accounting": {"Images": {"bytes": 1000}, "Build Cache": {"bytes": 200}}, "decoded_receipt": {
            "metrics": {"series_cardinality": 24},
            "traces": {"unique_records": 100, "delivered_records": 100, "decoded_bytes": 10000},
            "logs": {"unique_records": 50, "delivered_records": 51, "decoded_bytes": 5000}}}
    names = [("pair-0-disabled", False, 120), ("pair-0-enabled", True, 120),
        ("pair-1-enabled", True, 120), ("pair-1-disabled", False, 120),
        ("pair-2-disabled", False, 120), ("pair-2-enabled", True, 120), ("enabled-load", True, 300)]
    absolute = 0
    data = 1000
    accepted = 100
    for name, enabled, seconds in names:
        record["phases"][name] = {"duration_seconds": seconds, "collector_before": {}, "collector_after": {}, "target_requests_per_second_per_environment": 2,
            "concurrency_per_environment": 4, "environments": {
            env: {"attempted": seconds * 2, "success": seconds * 2, "errors": 0,
                "achieved_requests_per_second": 2, "target_coverage": 1, "p50_seconds": .02 if enabled else .01,
                "p95_seconds": .04 if enabled else .02, "peak_seconds": .06 if enabled else .03}
            for env in ("dev", "prod")}}
        for elapsed in range(0, seconds + 1, 5):
            row = {"phase": name, "timestamp_unix": absolute + elapsed, "field_max_gap_seconds": 5, "collector": {},
                "generator_cpu_percent": 2, "generator_memory_bytes": 200,
                "host_cpu_percent": 20 if enabled else 10, "host_memory_bytes": 10000,
                "services": {}, "aggregate_cpu_percent": 0, "private_fixture_other_bytes": 1024,
                "storage": {"/metrics": 1000, "/grafana": 1000,
                    **{signal: data + elapsed * (10 if enabled else 0) for signal in ("traces", "logs", "metrics")}},
                "telemetry_storage_subsets": {"/metrics/wal": 400, "/metrics/chunks_head": 200},
                "app_storage": {env: {"pgdata_bytes_including_wal": 1000, "pg_wal_bytes_subset": 300,
                    "uploads_allocated_bytes": 200} for env in ("dev", "prod")},
                "container_log_bytes": {"unit-only": 100}, "receiver_health": {
                    signal: {"accepted": accepted + elapsed * (2 if enabled else 0)} for signal in ("traces", "logs", "metrics")}}
            for service in ("dev/app", "prod/app", "dev/db", "prod/db", "obs/collector", "obs/prometheus",
                "obs/grafana", "obs/control", "obs/traces", "obs/logs", "obs/metrics"):
                row["services"][service] = {"cpu_percent": 2 if enabled else 1,
                    "memory_bytes": 200 if enabled else 100, "cap_bytes": 256 * 1024 ** 2}
            row["aggregate_cpu_percent"] = sum(value["cpu_percent"] for value in row["services"].values())
            record["samples"].append(row)
        absolute += seconds
        data += seconds * (10 if enabled else 0)
        accepted += seconds * (2 if enabled else 0)
    for signal in ("traces", "logs", "metrics"):
        decoded = record["decoded_receipt"][signal]
        if signal == "metrics":
            decoded.update(unique_records=20, delivered_records=21, decoded_bytes=2000)
        decoded["duplicate_records"] = decoded["delivered_records"] - decoded["unique_records"]
    record["reconciliation"] = {signal: {"sdk_records_attempted": 120, "sdk_records_acked": 110,
        "sdk_failed_attempt_records": 10, "generated": 120, "sdk_queue_dropped": 10,
        "queued_at_shutdown": 0} for signal in ("traces", "logs", "metrics")}
    return record


class ReportTest(unittest.TestCase):
    def test_phase_loss_preserves_healthy_enqueue_failure_and_unknown_outage_boundaries(self):
        record = fixture()
        key = "otelcol_exporter_enqueue_failed_metric_points_total|otlp_http/metrics"
        record["phases"]["pair-0-enabled"].update(collector_before={key: 0}, collector_after={key: 16})
        record["phases"]["outage-collector"] = {"collector_before": None, "collector_after": None}
        report = build_report(record)["capacity"]["phase_signal_accounting"]
        cell = report["pair-0-enabled"]["collector_phase_boundary_counters"]["metrics"]["enqueue_failed"]
        self.assertEqual(cell, {"before": 0, "after": 16, "delta": 16, "status": "observed"})
        unknown = report["outage-collector"]["collector_phase_boundary_counters"]["metrics"]["enqueue_failed"]
        self.assertIsNone(unknown["delta"])
        self.assertEqual(unknown["status"], "absent-unknown")
        record["phases"]["pair-0-enabled"].update(collector_before={key: 16}, collector_after={key: 0})
        reset = build_report(record)["capacity"]["phase_signal_accounting"]["pair-0-enabled"]["collector_phase_boundary_counters"]["metrics"]["enqueue_failed"]
        self.assertIsNone(reset["delta"])
        self.assertEqual(reset["status"], "reset-unknown")

    def test_final_healthy_burst_loss_survives_outside_phase_windows(self):
        record = fixture()
        key = "otelcol_exporter_enqueue_failed_metric_points_total|otlp_http/metrics"
        record["post_stop_drain"] = {"polls": [{"collector_counters": {key: 16}}]}
        report = build_report(record)["capacity"]
        self.assertEqual(report["final_collector_export_observations"]["otlp_http/metrics"]["enqueue_failed"], 16)
        self.assertIsNone(report["final_collector_export_observations"]["otlp_http/logs"]["enqueue_failed"])
        self.assertIn("No zero-loss claim", report["loss_boundary_note"])

    def test_actual_shaped_stopped_collector_is_explicitly_unavailable_not_zero(self):
        record = fixture()
        row = copy.deepcopy(record["samples"][-1])
        row.update(phase="outage-collector", timestamp_unix=row["timestamp_unix"] + 5,
            stopped_destination="collector", service_availability={"obs/collector": {"running": False, "paused": False}},
            collector=None)
        del row["services"]["obs/collector"]
        record["samples"].append(row)
        report = build_report(record)["capacity"]
        observed = report["service_observation_availability"]["obs/collector"]
        self.assertEqual(observed["intentionally_stopped_samples"], 1)
        self.assertIsNone(observed["unavailable_values"])
        for changes in ({"phase": "enabled-load"}, {"stopped_destination": None},
            {"service_availability": {}}, {"service_availability": {"obs/collector": {"running": True, "paused": False}}}):
            invalid = copy.deepcopy(record)
            invalid["samples"][-1].update(changes)
            with self.assertRaises(Failure):
                build_report(invalid)

    def test_three_pairs_report_app_telemetry_generator_host_deltas_and_variation(self):
        result = build_report(fixture())
        self.assertEqual(len(result["overhead"]["pairs"]), 3)
        self.assertEqual(result["overhead"]["pairs"][1]["order"], ["enabled", "disabled"])
        for pair in result["overhead"]["pairs"]:
            self.assertEqual(pair["resource_deltas"]["apps"]["cpu_percent"]["mean_enabled_minus_disabled"], 2)
            self.assertAlmostEqual(pair["latency_deltas"]["dev"]["p95_seconds"], .02)
            self.assertEqual(set(pair["actual_phases"]["enabled"]["resources"]), {
                "apps", "application_dependencies", "telemetry", "generators", "whole_host", "dev/app", "prod/app"})
        self.assertEqual(result["overhead"]["delta_variation_across_three_pairs"]["apps/cpu_percent"]["population_stddev"], 0)

    def test_disabled_time_cannot_dilute_healthy_enabled_growth_and_reserves_are_explicit(self):
        report = build_report(fixture())["capacity"]
        self.assertEqual(report["maximum_healthy_allocated_growth_bytes_per_second"]["telemetry/traces"], 10)
        self.assertEqual(report["daily_ingestion_projection_bytes_by_component"]["telemetry/traces"], 10 * 86400 * 2)
        self.assertEqual(report["oracle_reserved_cpu_fraction"], .2)
        self.assertGreaterEqual(report["oracle_reserved_memory_bytes"], 1.5 * 1024 ** 3)
        self.assertGreaterEqual(report["fixed_reserves_bytes"]["backup_two_copies_minimum_1GiB"], 1024 ** 3)
        self.assertEqual(report["metric_series_cardinality"], 24)
        self.assertEqual(report["arm_ocpu_fit"], "unproven")
        self.assertEqual(report["hypothetical_6GB_memory_budget_bytes"], 6_000_000_000)

    def test_missing_actual_fields_or_target_coverage_fail_instead_of_fabricating_zero(self):
        cases = []
        record = fixture()
        del record["samples"][0]["private_fixture_other_bytes"]
        cases.append(record)
        record = fixture()
        record["phases"]["pair-0-disabled"]["environments"]["dev"]["target_coverage"] = .8
        cases.append(record)
        record = fixture()
        record["samples"][0]["field_max_gap_seconds"] = 6
        cases.append(record)
        for record in cases:
            with self.assertRaises(Failure):
                build_report(record)

    def test_full_report_refuses_cross_job_functional_or_preflight_as_capacity(self):
        for part in ("preflight", "functional"):
            record = fixture()
            record["part"] = part
            with self.assertRaises(Failure):
                build_report(record)

    def test_zero_baseline_does_not_invent_a_relative_percentage(self):
        record = fixture()
        for row in record["samples"]:
            if row["phase"].endswith("disabled"):
                row["services"]["dev/app"]["cpu_percent"] = 0
        value = build_report(record)["overhead"]["pairs"][0]["resource_deltas"]["dev/app"]["cpu_percent"]
        self.assertIsNone(value["relative_percent"])
        self.assertEqual(value["mean_enabled_minus_disabled"], 2)

    def test_invalid_numeric_measurements_never_turn_into_zero(self):
        for invalid in (None, float("nan"), float("inf"), -1, True, "3"):
            for field in ("host_cpu_percent", "generator_memory_bytes", "private_fixture_other_bytes"):
                record = fixture()
                record["samples"][0][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(Failure):
                    build_report(record)

    def test_actual_paired_order_and_unequal_observed_intervals(self):
        record = fixture()
        rows = [row for row in record["samples"] if row["phase"] == "pair-0-enabled"]
        for row in rows:
            row["timestamp_unix"] += 10000
        with self.assertRaises(Failure):
            build_report(record)
        record = fixture()
        # Different measurement lengths must use their own elapsed seconds.
        report = build_report(record)["capacity"]
        windows = report["enabled_healthy_windows"]
        self.assertNotEqual(windows[0]["observed_seconds"], windows[1]["observed_seconds"])
        self.assertTrue(all(window["allocated_growth_bytes_per_second"]["telemetry/traces"] == 10 for window in windows))

    def test_retention_fixed_startup_wal_and_physical_images(self):
        record = fixture()
        record["expanded_image_bytes_by_role"] = {"application": 99999999, "same-image": 99999999}
        report = build_report(record)["capacity"]
        self.assertEqual(report["static_expanded_image_upper_bound_bytes"], 1200)
        self.assertEqual(report["configured_retention"]["prometheus_retention_size_bytes"], 536870912)
        self.assertEqual(report["retention_bounded_projection"]["7d"]["allocated_bytes_by_component"]["telemetry/traces"], 128 * 1024 ** 2)
        self.assertEqual(report["seven_day_unbounded_ingestion_storage_bytes"] - report["daily_conservative_storage_projection_bytes"],
            6 * sum(report["daily_ingestion_projection_bytes_by_component"].values()))
        self.assertIn("dev_postgres_WAL", report["WAL_head_subset_bytes_not_added_twice"])
        self.assertNotIn("dev/pg_wal", report["initial_allocated_data_bytes_by_component"])
        self.assertTrue(all(value["peak"] is None for value in report["observed_queue_counters"].values()))

    def test_only_allowlisted_output_and_fixed_failure_messages(self):
        import json
        record = fixture()
        canary = "PRIVATE-PAYLOAD-PATH-ID-CANARY"
        record["private_payload"] = canary
        record["application_image_id"] = canary
        record["phase_host_fingerprint"] = canary
        record["decoded_receipt"]["traces"]["private_body"] = canary
        self.assertNotIn(canary, json.dumps(build_report(record)))
        record["samples"][0]["storage"][canary] = 1
        with self.assertRaises(Failure) as raised:
            build_report(record)
        self.assertNotIn(canary, str(raised.exception))

    def test_unhealthy_window_cannot_contribute_rates(self):
        record = fixture()
        record["samples"][-1]["receiver_health"]["logs"] = None
        with self.assertRaises(Failure):
            build_report(record)

    def test_metric_attempts_are_not_unique_loss(self):
        record = fixture()
        record["reconciliation"]["metrics"]["generated"] = 25
        values = build_report(record)["capacity"]["signal_accounting"]
        self.assertIsNone(values["metrics"]["missing_unique_after_settle"])
        self.assertEqual(values["metrics"]["datapoint_observations_not_uniquely_stored_after_settle"], 5)
        self.assertEqual(values["traces"]["missing_unique_after_settle"], 20)
        self.assertFalse(values["metrics"]["failed_attempts_are_unique_loss"])

    def test_counter_reset_missing_latency_and_nan_caps_fail(self):
        records = []
        record = fixture()
        record["samples"][-2]["receiver_health"]["traces"]["accepted"] = 99999999
        records.append(record)
        record = fixture()
        del record["phases"]["pair-0-disabled"]["environments"]["dev"]["p95_seconds"]
        records.append(record)
        record = fixture()
        record["samples"][0]["services"]["dev/app"]["cap_bytes"] = float("nan")
        records.append(record)
        for record in records:
            with self.assertRaises(Failure):
                build_report(record)
