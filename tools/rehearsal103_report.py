"""Postprocess actual same-host samples; never synthesize runtime observations."""
from collections import defaultdict
import math
import re
import statistics

from tools.rehearsal101 import percentile, require


SIGNALS = ("traces", "logs", "metrics")
SERVICE_NAMES = {env + "/" + service for env in ("dev", "prod")
    for service in ("app", "db", "smtp", "proxy", "migrate", "uploads-init")} | {
    "obs/" + service for service in (*SIGNALS, "collector", "prometheus", "grafana", "control")}
STORAGE_NAMES = {"/metrics", "/grafana", *SIGNALS}
REQUIRED_SERVICES = {"dev/app", "prod/app", "dev/db", "prod/db", "obs/control", "obs/collector",
    "obs/prometheus", "obs/grafana", "obs/traces", "obs/logs", "obs/metrics"}


def number(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
        "report-numeric-observation-invalid")
    return value


def source_metadata(record):
    # Never serialize arbitrary host identifiers or free-form strings.
    source = record["source"]
    require(isinstance(source, str) and re.fullmatch(r"[0-9a-f]{40}", source), "report-source-invalid")
    return {"source": source}


def distribution(values):
    require(bool(values) and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values), "report-observation-unavailable")
    return {"samples": len(values), "mean": statistics.fmean(values), "p50": percentile(values, .5),
        "p95": percentile(values), "peak": max(values)}


def validate_services(row, allow_intentional_outage=False):
    missing = REQUIRED_SERVICES - set(row["services"])
    if missing:
        require(allow_intentional_outage and missing == {"obs/collector"}
            and row["phase"] == "outage-collector" and row.get("stopped_destination") == "collector"
            and row.get("service_availability", {}).get("obs/collector") == {"running": False, "paused": False},
            "report-service-group-missing")
    for name, value in row["services"].items():
        require(name in SERVICE_NAMES, "report-service-not-allowlisted")
        for field in ("cpu_percent", "memory_bytes", "cap_bytes"):
            number(value[field])
    return missing


def resource_groups(row):
    validate_services(row)
    groups = {name: {"cpu_percent": 0, "memory_bytes": 0} for name in (
        "apps", "application_dependencies", "telemetry", "generators")}
    for name, value in row["services"].items():
        require(name in SERVICE_NAMES, "report-service-not-allowlisted")
        number(value["cpu_percent"])
        number(value["memory_bytes"])
        number(value["cap_bytes"])
        kind = ("generators" if name == "obs/control" else "telemetry" if name.startswith("obs/")
            else "apps" if name.endswith("/app") else "application_dependencies")
        groups[kind]["cpu_percent"] += value["cpu_percent"]
        groups[kind]["memory_bytes"] += value["memory_bytes"]
    groups["generators"]["cpu_percent"] += number(row["generator_cpu_percent"])
    groups["generators"]["memory_bytes"] += number(row["generator_memory_bytes"])
    groups["whole_host"] = {"cpu_percent": row["host_cpu_percent"], "memory_bytes": row["host_memory_bytes"]}
    for environment in ("dev", "prod"):
        require(environment + "/app" in row["services"], "report-app-observation-missing")
        groups[environment + "/app"] = {field: row["services"][environment + "/app"][field]
            for field in ("cpu_percent", "memory_bytes")}
    return groups


def allocated_storage(row):
    require(set(row["storage"]) == STORAGE_NAMES, "report-storage-not-allowlisted")
    require(set(row["app_storage"]) == {"dev", "prod"}, "report-environment-not-allowlisted")
    values = {"telemetry/" + name: number for name, number in row["storage"].items()}
    for environment, data in row["app_storage"].items():
        values[environment + "/pgdata_including_wal"] = data["pgdata_bytes_including_wal"]
        values[environment + "/uploads"] = data["uploads_allocated_bytes"]
    values["owned_container_logs"] = sum(number(value) for value in row["container_log_bytes"].values())
    require("private_fixture_other_bytes" in row, "private-fixture-storage-observation-missing")
    values["private_fixture_other"] = row["private_fixture_other_bytes"]
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values.values()), "report-storage-observation")
    return values


def phase_report(rows):
    groups = [resource_groups(row) for row in rows]
    result = {group: {field: distribution([value[group][field] for value in groups])
        for field in ("cpu_percent", "memory_bytes")} for group in groups[0]}
    require(all(set(row["services"]) == set(rows[0]["services"]) for row in rows), "report-service-coverage")
    services = sorted(rows[0]["services"])
    return {"resources": result, "services": {name: {field: distribution([row["services"][name][field] for row in rows])
        for field in ("cpu_percent", "memory_bytes")} for name in services},
        "actual_max_field_gap_seconds": max(number(row["field_max_gap_seconds"]) for row in rows)}


def variation(values):
    return {"mean": statistics.fmean(values), "minimum": min(values), "maximum": max(values),
        "population_stddev": statistics.pstdev(values)}


def overhead(record, byphase):
    pairs, variations = [], defaultdict(list)
    for index in range(3):
        names = {mode: "pair-" + str(index) + "-" + mode for mode in ("enabled", "disabled")}
        reports = {}
        for mode, name in names.items():
            phase = record["phases"][name]
            require(number(phase["duration_seconds"]) >= 120 and len(byphase[name]) >= 24, "paired-run-coverage")
            require(set(phase["environments"]) == {"dev", "prod"} and all(number(v["errors"]) == 0 and number(v["target_coverage"]) >= .98 for v in phase["environments"].values()), "paired-request-target")
            reports[mode] = phase_report(byphase[name])
            reports[mode]["duration_seconds"] = number(phase["duration_seconds"])
            reports[mode]["environments"] = {env: {key: number(phase["environments"][env][key])
                for key in ("attempted", "success", "errors", "achieved_requests_per_second", "target_coverage",
                    "p50_seconds", "p95_seconds", "peak_seconds")} for env in ("dev", "prod")}
            require(number(phase["target_requests_per_second_per_environment"]) == 2 and
                number(phase["concurrency_per_environment"]) <= 4, "paired-workload-invalid")
            stamps = [number(row["timestamp_unix"]) for row in byphase[name]]
            require(all(0 < b - a <= 5 for a, b in zip(stamps, stamps[1:])) and
                stamps[-1] - stamps[0] >= phase["duration_seconds"] - 5, "paired-sample-duration")
            require(reports[mode]["actual_max_field_gap_seconds"] <= 5, "paired-field-gap")
        differences = {}
        for group in reports["enabled"]["resources"]:
            differences[group] = {}
            for field in ("cpu_percent", "memory_bytes"):
                baseline = reports["disabled"]["resources"][group][field]["mean"]
                enabled = reports["enabled"]["resources"][group][field]["mean"]
                delta = enabled - baseline
                differences[group][field] = {"mean_enabled_minus_disabled": delta,
                    "relative_percent": 100 * delta / baseline if baseline > 0 else None}
                variations[group + "/" + field].append(delta)
        latencies = {}
        for environment in ("dev", "prod"):
            latencies[environment] = {}
            for field in ("p50_seconds", "p95_seconds", "peak_seconds"):
                baseline = record["phases"][names["disabled"]]["environments"][environment][field]
                enabled = record["phases"][names["enabled"]]["environments"][environment][field]
                number(baseline)
                number(enabled)
                latencies[environment][field] = enabled - baseline
                variations[environment + "/" + field].append(enabled - baseline)
        actual_order = sorted(names, key=lambda mode: byphase[names[mode]][0]["timestamp_unix"])
        expected_order = ["disabled", "enabled"] if index % 2 == 0 else ["enabled", "disabled"]
        require(actual_order == expected_order, "paired-order-invalid")
        require(byphase[names[actual_order[0]]][-1]["timestamp_unix"] <=
            byphase[names[actual_order[1]]][0]["timestamp_unix"], "paired-phase-overlap")
        pairs.append({"pair": index, "order": actual_order,
            "actual_phases": reports, "resource_deltas": differences, "latency_deltas": latencies})
    return {**source_metadata(record), "pairs": pairs,
        "delta_variation_across_three_pairs": {name: variation(values) for name, values in variations.items()},
        "cpu_unit": "percentage points;100%=one logical CPU, not an ARM/OCPU equivalence",
        "cost_scope": "Whole instrumentation system including SDK observer and fixture; not pure SDK overhead; same-host/build prerequisite enforced by controller"}


def healthy_windows(record, byphase):
    result = []
    names = ["enabled-load", *("pair-" + str(i) + "-enabled" for i in range(3))]
    for name in names:
        rows = byphase[name]
        require(len(rows) >= 24, "healthy-window-samples")
        first, last = rows[0], rows[-1]
        stamps = [number(row["timestamp_unix"]) for row in rows]
        require(all(0 < right - left <= 5 for left, right in zip(stamps, stamps[1:])), "healthy-window-gap")
        elapsed = stamps[-1] - stamps[0]
        require(all(row["receiver_health"][signal] is not None for row in rows for signal in SIGNALS), "healthy-window-receipt-missing")
        require(all(row.get("collector") is not None for row in rows), "healthy-window-collector-missing")
        require(elapsed >= record["phases"][name]["duration_seconds"] - 5, "healthy-window-time")
        begin, end = allocated_storage(first), allocated_storage(last)
        require(set(begin) == set(end), "healthy-storage-fields")
        deltas = {key: end[key] - begin[key] for key in begin}
        growth = {key: max(0, delta) for key, delta in deltas.items()}
        rates = {}
        for signal in ("traces", "logs", "metrics"):
            counts = [number(row["receiver_health"][signal]["accepted"]) for row in rows]
            require(all(b >= a for a, b in zip(counts, counts[1:])), "healthy-receipt-reset")
            left, right = first["receiver_health"][signal], last["receiver_health"][signal]
            require(left is not None and right is not None and number(right["accepted"]) >= number(left["accepted"]), "healthy-receipt-counter")
            require(counts[-1] > counts[0], "healthy-receipt-no-progress")
            rates[signal] = {"actual_deliveries": right["accepted"] - left["accepted"],
                "delivered_records_per_second": (right["accepted"] - left["accepted"]) / elapsed}
        result.append({"phase": name, "observed_seconds": elapsed, "samples": len(rows),
            "actual_start_allocated_bytes": begin, "actual_end_allocated_bytes": end,
            "actual_allocated_delta_bytes": deltas, "allocated_growth_bytes": growth, "allocated_growth_bytes_per_second": {key: value / elapsed for key, value in growth.items()},
            "actual_signal_delivery_rates": rates,
            "rate_note": "Observed deliveries include retry duplicates; unique full-run receipt/loss is reconciled separately"})
    return result


def _build_report(record):
    source_metadata(record)
    require(record["part"] == "capacity", "capacity-host-only")
    byphase = defaultdict(list)
    stamps = [number(row["timestamp_unix"]) for row in record["samples"]]
    require(bool(stamps) and all(b >= a for a, b in zip(stamps, stamps[1:])), "report-sample-order")
    for row in record["samples"]:
        validate_services(row, allow_intentional_outage=True)
        for field in ("generator_cpu_percent", "generator_memory_bytes", "host_cpu_percent", "host_memory_bytes"):
            number(row[field])
        number(row["aggregate_cpu_percent"])
        require(number(row["field_max_gap_seconds"]) <= 5, "report-field-gap")
        byphase[row["phase"]].append(row)
    require(number(record["phases"]["enabled-load"]["duration_seconds"]) >= 300, "enabled-load-coverage")
    require(number(record["outages"]["collector"]["seconds"]) >= 60
        and number(record["recoveries"]["collector"]["fresh_three_signal_seconds"]) <= 120, "same-host-outage-recovery")
    windows = healthy_windows(record, byphase)
    maximum_rates = {key: max(window["allocated_growth_bytes_per_second"][key] for window in windows)
        for key in windows[0]["allocated_growth_bytes_per_second"]}
    daily = {key: math.ceil(rate * 86400 * 2) for key, rate in maximum_rates.items()}
    initial = allocated_storage(record["samples"][0])
    peak_app_state = max(sum(value for key, value in allocated_storage(row).items()
        if key.startswith(("dev/", "prod/"))) for row in record["samples"])
    backup_reserve = max(1024 ** 3, 2 * peak_app_state)
    reserves = {"backup_two_copies_minimum_1GiB": backup_reserve, "prometheus_WAL_head_compaction": 512 * 1024 ** 2,
        "receiver_inode_filesystem_metadata": 3 * 8 * 1024 ** 2, "all_configured_container_log_rotation": 80 * 1024 ** 2}
    fixed = sum(reserves.values())
    service_names = {name for row in record["samples"] for name in row["services"]}
    peaks = {name: max(row["services"][name]["memory_bytes"] for row in record["samples"] if name in row["services"])
        for name in service_names}
    caps = {name: max(row["services"][name]["cap_bytes"] for row in record["samples"] if name in row["services"])
        for name in service_names}
    peak_generator = max(row["generator_memory_bytes"] for row in record["samples"])
    peak_cpu = max(row["aggregate_cpu_percent"] + row["generator_cpu_percent"] for row in record["samples"])
    base = sum(initial.values())
    # Physical accounting is an actual Docker observation. Role-expanded sizes are
    # retained by the controller only; they overlap and must never be summed here.
    images = number(record["docker_disk_accounting"]["Images"]["bytes"])
    cache = number(record["docker_disk_accounting"]["Build Cache"]["bytes"])
    images += cache
    capacity = {**source_metadata(record),
        "enabled_healthy_windows": windows, "projection_method": "Maximum component growth rate across healthy enabled windows only;2x safety; disabled/restarts/outages never dilute rates",
        "maximum_healthy_allocated_growth_bytes_per_second": maximum_rates,
        "daily_ingestion_projection_bytes_by_component": daily, "initial_allocated_data_bytes_by_component": initial,
        "fixed_reserves_bytes": reserves,
        "fixed_reserves_note": "Additional future WAL/head/compaction, backup and log-rotation allowance; measured WAL/head remain subsets of existing data and are never added as separate observed bytes", "static_expanded_image_upper_bound_bytes": images,
        "observed_docker_images_bytes": images - cache, "observed_docker_build_cache_bytes": cache,
        "static_image_note": "Actual daemon Images plus Build Cache category totals, conservative host upper bound; categories may overlap; not a physical deduplication claim or role-size sum",
        "daily_conservative_storage_projection_bytes": images + base + sum(daily.values()) + fixed,
        "seven_day_unbounded_ingestion_storage_bytes": images + base + 7 * sum(daily.values()) + fixed,
        "retention_note": "7d is ingestion projection, not7d configured retention. Receivers cap24h/128MiB each; cap may evict sooner.",
        "receiver_projected_cap_hours": {signal: min(24, 128 * 1024 ** 2 / (2 * maximum_rates["telemetry/" + signal]) / 3600)
            if maximum_rates["telemetry/" + signal] > 0 else None for signal in ("traces", "logs", "metrics")},
        "peak_observed_service_memory_bytes": peaks, "declared_service_memory_caps_bytes": caps,
        "peak_observed_generator_memory_bytes": peak_generator, "oracle_reserved_memory_bytes": int(1.5 * 1024 ** 3),
        "oracle_reserved_cpu_fraction": .2, "minimum_logical_cpus_after_20percent_reserve": peak_cpu / 100 / .8,
        "memory_from_declared_caps_plus_1_5GiB_reserve_bytes": sum(caps.values()) + peak_generator + int(1.5 * 1024 ** 3),
        "hypothetical_6GB_memory_budget_bytes": 6_000_000_000,
        "hypothetical_6GB_cap_sum_fit": sum(caps.values()) + peak_generator + int(1.5 * 1024 ** 3) <= 6_000_000_000,
        "hypothetical_1OCPU_budget": 1,
        "hypothetical_1OCPU_fit": "unproven; x64 logical CPU measurements do not establish ARM/OCPU capacity",
        "arm_ocpu_fit": "unproven", "hosted_activation": "blocked",
        "limitations": "Short local sampled runs; no production query/retention soak, no ARM/OCPU fit; peaks are sampled observations, not absolute maxima"}
    subsets = {"prometheus_WAL": [row["telemetry_storage_subsets"]["/metrics/wal"] for row in record["samples"]],
        "prometheus_head": [row["telemetry_storage_subsets"]["/metrics/chunks_head"] for row in record["samples"]]}
    for environment in ("dev", "prod"):
        subsets[environment + "_postgres_WAL"] = [row["app_storage"][environment]["pg_wal_bytes_subset"] for row in record["samples"]]
    capacity["WAL_head_subset_bytes_not_added_twice"] = {key: distribution(values) for key, values in subsets.items()}
    capacity["metric_series_cardinality"] = number(record["decoded_receipt"]["metrics"]["series_cardinality"])
    capacity["actual_sampled_trace_log_counts_and_decoded_bytes"] = {signal: {
        key: number(record["decoded_receipt"][signal][key]) for key in ("unique_records", "delivered_records", "decoded_bytes")}
        for signal in ("traces", "logs")}
    receiver_cap = 128 * 1024 ** 2
    prometheus_cap = 512 * 1024 ** 2
    capacity["configured_retention"] = {
        "trace_log_max_age_seconds": 86400, "trace_log_each_storage_cap_bytes": receiver_cap,
        "prometheus_retention_seconds": 86400, "prometheus_retention_size_bytes": prometheus_cap,
        "prometheus_argument": "512MB", "prometheus_size_unit": "binary; 536870912 bytes",
        "prometheus_cap_note": "Retention size does not bound WAL/head; explicit extra reserve retained"}
    # Keep the unbounded ingestion projection visible. Also report bounded active
    # retention inventory: fixed/startup and backups remain at both horizons.
    bounded = {}
    for days in (1, 7):
        parts = {}
        for key, initial_bytes in initial.items():
            growth = daily[key] * days
            if key in {"telemetry/traces", "telemetry/logs", "telemetry/metrics"}:
                parts[key] = receiver_cap
            elif key == "telemetry//metrics":
                parts[key] = max(initial_bytes, prometheus_cap)
            elif key == "owned_container_logs":
                parts[key] = max(initial_bytes, reserves["all_configured_container_log_rotation"])
            else:
                parts[key] = initial_bytes + growth
        bounded[str(days) + "d"] = {"allocated_bytes_by_component": parts,
            "total_bytes_including_fixed_reserves": images + sum(parts.values()) + fixed}
    capacity["retention_bounded_projection"] = bounded
    capacity["oracle_disk_free_reserve"] = "max(4GiB,20% actual host disk); backing disk capacity required to assess fit"
    capacity["observed_queue_counters"] = queue_observations(record["samples"])
    capacity["phase_signal_accounting"] = phase_signal_accounting(record, byphase)
    final = record.get("post_stop_drain", {}).get("polls", [])
    final = final[-1]["collector_counters"] if final else {}
    capacity["final_collector_export_observations"] = {component: {kind.rstrip("_"): final.get(
        "otelcol_exporter_" + kind + ("spans" if component.endswith("traces") else "log_records"
            if component.endswith("logs") else "metric_points") + "_total|" + component)
        for kind in ("sent_", "send_failed_", "enqueue_failed_")}
        for component in ("otlp_http/traces", "otlp_http/logs", "otlp_http/metrics", "prometheusremotewrite")}
    require(all(value is None or type(value) in (int, float) and math.isfinite(value) and value >= 0
        for counter in capacity["final_collector_export_observations"].values() for value in counter.values()), "final-collector-counter-invalid")
    capacity["loss_boundary_note"] = "Final counters include preparation, transition, privacy and shutdown bursts outside measured phase boundaries; phase deltas cannot erase that loss. Missing counters remain unknown. No zero-loss claim."
    capacity["service_observation_availability"] = {name: {
        "observed_samples": sum(name in row["services"] for row in record["samples"]),
        "intentionally_stopped_samples": sum(name not in row["services"] for row in record["samples"]),
        "unavailable_values": None} for name in sorted(REQUIRED_SERVICES)}
    capacity["signal_accounting"] = signal_accounting(record)
    capacity["receiver_counters"] = {signal: {field: counter_summary([
        row["receiver_health"][signal][field] for row in record["samples"]
        if row["receiver_health"].get(signal) is not None and field in row["receiver_health"][signal]])
        for field in ("accepted", "refused_requests", "refused_records", "unknown_refused_requests", "evicted_files")}
        for signal in SIGNALS}
    return {"overhead": overhead(record, byphase), "capacity": capacity, "capacity_acceptance": True}


def counter_summary(values):
    values = [number(value) for value in values]
    return {"observed_samples": len(values), "peak": max(values) if values else None,
        "first": values[0] if values else None, "last": values[-1] if values else None,
        "counter_resets_observed": sum(b < a for a, b in zip(values, values[1:])) if values else None}


def counter_delta(before, after):
    for value in (before, after):
        if value is not None:
            number(value)
    known = before is not None and after is not None
    reset = known and after < before
    return {"before": before, "after": after, "delta": after - before if known and not reset else None,
        "status": "reset-unknown" if reset else "observed" if known else "absent-unknown"}


def phase_signal_accounting(record, byphase):
    result = {}
    for name, phase in record["phases"].items():
        require(re.fullmatch(r"pair-[0-2]-(?:enabled|disabled)|enabled-load|outage-job-healthy-baseline|sdk-backpressure-collector-paused|(?:outage|recovery)-(?:collector|traces|logs|metrics|prometheus)(?:-[0-9]{1,2})?", name),
            "report-phase-not-allowlisted")
        require("collector_before" in phase and "collector_after" in phase, "phase-counter-boundary-missing")
        before, after = phase["collector_before"], phase["collector_after"]
        counters = {}
        for signal in (*SIGNALS, "prometheusremotewrite"):
            component = signal if signal == "prometheusremotewrite" else "otlp_http/" + signal
            unit = "spans" if signal == "traces" else "log_records" if signal == "logs" else "metric_points"
            counters[signal] = {}
            for kind in ("sent_", "send_failed_", "enqueue_failed_"):
                key = "otelcol_exporter_" + kind + unit + "_total|" + component
                counters[signal][kind.rstrip("_")] = counter_delta(
                    before.get(key) if before is not None else None, after.get(key) if after is not None else None)
        windows = {}
        for signal in SIGNALS:
            rows = [row for row in byphase[name] if row["receiver_health"].get(signal) is not None]
            windows[signal] = {"observed_samples": len(rows), "snapshot_window_seconds":
                rows[-1]["timestamp_unix"] - rows[0]["timestamp_unix"] if len(rows) >= 2 else None,
                "delivered_records": counter_delta(rows[0]["receiver_health"][signal]["accepted"] if rows else None,
                    rows[-1]["receiver_health"][signal]["accepted"] if len(rows) >= 2 else None)}
        result[name] = {"collector_phase_boundary_counters": counters, "receiver_sample_windows": windows,
            "units": "Spans/log records or timestamped metric datapoint observations; failed attempts are not unique loss",
            "boundary_note": "Collector phase boundaries and receiver sample windows differ; do not subtract these windows as exact unique loss"}
    return result


def signal_accounting(record):
    result = {}
    for signal in SIGNALS:
        decoded = record["decoded_receipt"][signal]
        counts = {key: number(decoded[key]) for key in
            ("unique_records", "delivered_records", "duplicate_records", "decoded_bytes")}
        require(counts["delivered_records"] == counts["unique_records"] + counts["duplicate_records"],
            "report-delivery-reconciliation")
        reconciled = record["reconciliation"][signal]
        counts.update({key: number(reconciled[key]) for key in (
            "sdk_records_attempted", "sdk_records_acked", "sdk_failed_attempt_records")})
        if signal in ("traces", "logs"):
            counts.update({key: number(reconciled[key]) for key in
                ("generated", "sdk_queue_dropped", "queued_at_shutdown")})
            require(counts["generated"] >= counts["unique_records"], "report-unique-loss-invalid")
            counts["missing_unique_after_settle"] = counts["generated"] - counts["unique_records"]
            counts["unit"] = "individual spans or log records; attempted exports may repeat"
        else:
            counts["missing_unique_after_settle"] = None
            attempted = number(reconciled["generated"])
            require(attempted >= counts["unique_records"], "report-metric-observation-accounting")
            counts["sdk_generated_datapoint_observations"] = attempted
            counts["datapoint_observations_not_uniquely_stored_after_settle"] = attempted - counts["unique_records"]
            counts["metric_accounting_boundary"] = "Timestamped cumulative data point observations; adapter retries disabled; difference is not lost requests, metric increments, or time series"
            counts["unit"] = "exported metric data points; repeated cumulative observations are not unique generated events"
        counts["failed_attempts_are_unique_loss"] = False
        result[signal] = counts
    return result


def queue_observations(rows):
    # Only known Collector counter prefixes/components; no arbitrary label strings.
    prefixes = ("otelcol_exporter_queue_size", "otelcol_exporter_queue_capacity",
        "otelcol_exporter_enqueue_failed_spans", "otelcol_exporter_enqueue_failed_log_records",
        "otelcol_exporter_enqueue_failed_metric_points", "otelcol_receiver_accepted_spans",
        "otelcol_receiver_accepted_log_records", "otelcol_receiver_accepted_metric_points")
    components = {"otlp_http/" + signal for signal in SIGNALS} | {"prometheusremotewrite"}
    prefixes += ("otelcol_exporter_sent_spans", "otelcol_exporter_sent_log_records",
        "otelcol_exporter_sent_metric_points", "otelcol_exporter_send_failed_spans",
        "otelcol_exporter_send_failed_log_records", "otelcol_exporter_send_failed_metric_points")
    prefixes += tuple(prefix + "_total" for prefix in prefixes if "queue_" not in prefix)
    result = {}
    for prefix in prefixes:
        for component in sorted(components):
            key = prefix + "|" + component
            values = [number(row["collector"][key]) for row in rows
                if row.get("collector") is not None and key in row["collector"]]
            result[key] = {"observed_samples": len(values), "peak": max(values) if values else None}
    return result


def build_report(record):
    """Fail with fixed stage names only; private payloads never enter exceptions."""
    try:
        return _build_report(record)
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        from tools.rehearsal101 import Failure
        raise Failure("report-required-observation-invalid") from None
