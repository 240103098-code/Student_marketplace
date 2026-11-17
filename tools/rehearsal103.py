"""Actual Linux three-signal rehearsal. Explicit synthetic ownership only.

Reuses #101 immutable architecture/images/certificates/normal auth journeys and
cleanup without changing its source/evidence. All decoded storage stays private.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.parse
import uuid

from tools.rehearsal101 import (Rehearsal, Failure, ROOT, LABEL, CAPS, require,
    port, request, percentile, digest, metrics, failure_metadata)
from tools.rehearsal101_capacity import candidate, bytes_value, app_disk, host_cpu, grafana, query

SIGNALS = ("traces", "logs", "metrics")
PLANS = {
    "preflight": {"healthy_seconds": 15, "privacy": True, "capacity_acceptance": False},
    "capacity": {"paired_runs": 3, "paired_phase_seconds": 120, "enabled_load_seconds": 300,
        "outages": ["collector"], "outage_seconds": 60, "recovery_max_seconds": 120},
    "functional": {"baseline_seconds": 15, "sdk_backpressure_seconds": 12,
        "outages": ["collector", "traces", "logs", "metrics", "prometheus"],
        "outage_seconds": 60, "recovery_max_seconds": 120}}


def attribute_map(values):
    require(len(values) <= 8 and len({item["key"] for item in values}) == len(values), "attribute-count-or-duplicate")
    return {item["key"]: next(iter(item["value"].values())) for item in values}


def validate_http_attributes(attrs, routes):
    require(set(attrs) == {"http.route", "http.request.method", "http.response.status_class", "outcome"}, "http-attribute-allowlist")
    require(attrs["http.route"] in routes, "route-template-allowlist")
    require(attrs["http.request.method"] in {"GET", "POST", "PATCH", "DELETE", "PUT", "HEAD", "OPTIONS", "OTHER"}, "method-allowlist")
    require(attrs["http.response.status_class"] in {"1xx", "2xx", "3xx", "4xx", "5xx", "other"}
        and attrs["outcome"] in {"success", "error"}, "outcome-status-allowlist")


def decoded(directory, signal):
    """Read only exact-owned decoded receiver files, bounded by receiver limits."""
    for path in sorted((directory / signal).glob("*.json")):
        require(not path.is_symlink() and path.stat().st_size <= 524288, "decoded-file-bound")
        yield json.loads(path.read_bytes())


def records(document, signal):
    plural, scope, leaf = {"traces": ("resourceSpans", "scopeSpans", "spans"),
        "logs": ("resourceLogs", "scopeLogs", "logRecords"),
        "metrics": ("resourceMetrics", "scopeMetrics", "metrics")}[signal]
    for resource in document.get(plural, []):
        for group in resource.get(scope, []):
            for record in group.get(leaf, []):
                yield resource, group, record


def identity(signal, resource, record):
    if signal == "traces":
        return (record["traceId"], record["spanId"])
    if signal == "logs":
        return (record.get("traceId"), record.get("spanId"), record.get("timeUnixNano"), record.get("body", {}).get("stringValue"))
    return digest(json.dumps([resource.get("resource"), record], sort_keys=True).encode())


def stored_counts(directory):
    result = {}
    for signal in SIGNALS:
        files = list((directory / signal).glob("*.json"))
        result[signal] = {"files": len(files), "bytes": sum(p.stat().st_size for p in files),
                          "newest_unix": max((p.stat().st_mtime for p in files), default=0)}
    return result


class Controller(Rehearsal):
    def __init__(self, part):
        super().__init__()
        self.part = part
        self.deadline = time.monotonic() + 1570
        self.record.update(issue=103, part=part, phases={}, samples=[],
            future_overhead="Measured only by this #103 run; production capacity remains unproven.")
        self.canaries = ["PRIVATE103_" + uuid.uuid4().hex + "+/=:@" for _ in range(12)]
        self.stacks = []
        self.transition_seconds = 0

    def api(self, stack, path, **kwargs):
        # Inherited helper's8s timeout is not used: every actual request<=5s.
        method = kwargs.pop("method", "GET")
        headers = dict(kwargs.pop("headers", None) or {})
        value = kwargs.pop("value", None)
        body = kwargs.pop("body", None)
        if value is not None:
            body = json.dumps(value).encode()
            headers["Content-Type"] = "application/json"
        for argument, header, prefix in (("token", "Authorization", "Bearer "), ("cookie", "Cookie", ""), ("origin", "Origin", "")):
            item = kwargs.pop(argument, None)
            if item:
                headers[header] = prefix + item
        require(not kwargs, "api-fixture-arguments")
        return request(stack["origin"], "/api" + path, method=method, body=body,
                       headers=headers, context=self.context, timeout=5)

    def observability(self):
        obs = candidate(self)
        config = obs["config"]
        collector = json.loads((obs["directory"] / "collector.json").read_text())
        collector["processors"]["batch"].update(send_batch_size=16, send_batch_max_size=16)
        # Each exporter has its own actual bounded request queue, including the
        # additional metrics receipt branch. Failed attempts are not unique loss.
        for signal in SIGNALS:
            key = "otlp_http/" + signal
            collector["exporters"][key] = {
                "endpoint": "http://" + signal + ":4318", "compression": "none", "timeout": "1s",
                "sending_queue": {"enabled": True, "sizer": "requests", "queue_size": 2, "num_consumers": 1,
                    "block_on_overflow": False, "wait_for_result": False,
                    "batch": {"sizer": "items", "min_size": 16, "max_size": 16, "flush_timeout": "100ms"}},
                "retry_on_failure": {"enabled": True, "initial_interval": "1s", "max_interval": "2s", "max_elapsed_time": "5s"}}
            collector["service"]["pipelines"][signal] = {"receivers": ["otlp"],
                "processors": ["memory_limiter", "batch"], "exporters": [key]}
        collector["service"]["pipelines"]["metrics"]["exporters"].append("prometheusremotewrite")
        collector["exporters"]["prometheusremotewrite"].update(timeout="1s", remote_write_queue={"enabled": True, "queue_size": 2, "num_consumers": 1})
        collector["exporters"]["prometheusremotewrite"]["resource_to_telemetry_conversion"] = {"enabled": True}
        collector["exporters"]["prometheusremotewrite"]["retry_on_failure"].update(max_elapsed_time="5s", max_interval="2s")
        (obs["directory"] / "collector.json").write_text(json.dumps(collector))
        config["networks"].update({name + "telemetry": {"internal": True, "labels": {LABEL: self.owner}}
                                    for name in ("dev", "prod")})
        config["services"]["collector"]["networks"] = ["default", "devtelemetry", "prodtelemetry"]
        for signal in SIGNALS:
            directory = obs["directory"] / signal
            directory.mkdir(mode=0o700)
            config["services"][signal] = {"image": self.image, "pull_policy": "never", "user": self.fixture_user,
                "command": ["python", "/receiver.py", "--signal", signal, "--private-directory", "/private"],
                "volumes": [str(ROOT / "tools/otel103_receiver.py") + ":/receiver.py:ro", str(directory) + ":/private"],
                "read_only": True, "cpus": .25, "mem_limit": "128m", "pids_limit": 32,
                "labels": {LABEL: self.owner}, "restart": "no", "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "logging": {"driver": "json-file", "options": {"max-size": "1m", "max-file": "2"}}}
        control = config["services"]["control"]
        control["command"] = ["python", "/control.py"]
        control["networks"] = ["default", "ingress", "devtelemetry", "prodtelemetry"]
        control["volumes"] = [str(ROOT / "ops/rehearsal103/control.py") + ":/control.py:ro",
            str(ROOT / "ops/rehearsal101/proxy.py") + ":/proxy101.py:ro", "metrics:/metrics:ro", "grafana:/grafana:ro"]
        for signal, internal in zip(SIGNALS, (14321, 14322, 14323)):
            selected = port()
            obs["endpoints"][signal] = "http://127.0.0.1:" + str(selected)
            control["ports"].append("127.0.0.1:" + str(selected) + ":" + str(internal))
        for name, internal in (("dev", 14324), ("prod", 14325)):
            selected = port()
            obs["endpoints"][name + "-sdk"] = "http://127.0.0.1:" + str(selected)
            control["ports"].append("127.0.0.1:" + str(selected) + ":" + str(internal))
        self.save(obs)
        validated = self.compose(obs, "run", "--rm", "--no-deps", "collector", "validate", "--config=/config/collector.json", timeout=30, okay=True)
        self.check("collector-three-pipeline-config-validation", validated.returncode == 0)
        self.record["collector_config_sha256"] = digest((obs["directory"] / "collector.json").read_bytes())
        self.compose(obs, "up", "-d", "--wait", "--wait-timeout", "90", timeout=110)
        self.obs = obs
        self.record["candidate_configuration"].update(components="Three actual OTLP/HTTP pipelines to separate private protobuf sinks; metrics additionally Prometheus/Grafana",
            queue_capacity_requests_each=2, queue_capacity_requests_total=8, queue_sizer="requests",
            queue_batch_max_items=16, retry_max_seconds=5, batch_points=16,
            receiver_retention_hours=24, receiver_logical_bytes_cap_each=128 * 1024 ** 2,
            receiver_file_cap_each=16384, receiver_filesystem_allocation_reserve_bytes_each=64 * 1024 ** 2,
            resource_conversion="Only explicit finite three-field application resource becomes Prometheus labels; avoids cross-environment series collision",
            receiver_memory_mib_each=128, receiver_cpu_each=.25)
        return obs

    def telemetry(self, enabled):
        transition_started = time.monotonic()
        for stack in self.stacks:
            if stack.get("fixture_installed"):
                self.collect_shutdown(stack)
            environment = stack["environment"]
            environment.update(TELEMETRY_ENABLED="true" if enabled else "false",
                TELEMETRY_ENDPOINT="http://collector:4318", TELEMETRY_VERSION=self.record["source"])
            environment.update(OTEL_RESOURCE_ATTRIBUTES="private=" + self.canaries[8], OTEL_SERVICE_NAME=self.canaries[9],
                OTEL_EXPORTER_OTLP_HEADERS=self.canaries[10], OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE=self.canaries[11],
                OTEL_EXPORTER_OTLP_CLIENT_KEY=self.canaries[11])
            config = stack["config"]
            config["networks"]["telemetry"] = {"external": True,
                "name": self.obs["project"] + "_" + stack["name"] + "telemetry"}
            config["services"]["app"]["networks"] = {"default": {}, "telemetry": {"aliases": [stack["name"] + "-app"]}}
            config["services"]["app"]["command"] = ["python", "-m", "uvicorn", "runtime103:create_app", "--factory",
                "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
            config["services"]["app"]["volumes"].append(str(ROOT / "ops/rehearsal103/runtime.py") + ":/app/runtime103.py:ro") if not any("runtime103.py" in v for v in config["services"]["app"]["volumes"]) else None
            probe = stack["directory"] / "canary-probe.json"
            probe.write_text(json.dumps(self.canaries))
            probe.chmod(0o644)
            if not any("canary-probe.json" in v for v in config["services"]["app"]["volumes"]):
                config["services"]["app"]["volumes"].append(str(probe) + ":/canary-probe.json:ro")
            self.save(stack)
            self.recreate_app(stack)
            stack["fixture_installed"] = True
            status, _, body = self.api(stack, "/auth/login", method="POST",
                value={"email": stack["email"], "password": stack["password"]})
            require(status == 200, "phase-normal-login")
            stack["token"] = json.loads(body)["access_token"]
        self.transition_seconds += time.monotonic() - transition_started
        require(self.transition_seconds <= 90, "app-transition-budget")

    def collect_shutdown(self, stack):
        started = time.monotonic()
        self.compose(stack, "stop", "--timeout", "10", "app", timeout=15)
        elapsed = time.monotonic() - started
        raw = self.compose(stack, "logs", "--no-color", "app", timeout=5).stdout
        values = [json.loads(line.split("TELEMETRY103_SHUTDOWN ", 1)[1]) for line in raw.splitlines() if "TELEMETRY103_SHUTDOWN " in line]
        require(len(values) == 1, "actual-app-shutdown-observation")
        value = values[0]
        if value["enabled"]:
            require("shutdown_seconds" in value["health"] and value["health"]["shutdown_seconds"] <= 10, "actual-sdk-shutdown-deadline")
            require("sdk_workers_alive_after_shutdown" in value and value["sdk_workers_alive_after_shutdown"] == 0, "sdk-worker-shutdown")
        value.update(environment=stack["name"], docker_stop_seconds=elapsed)
        self.record.setdefault("app_shutdowns", []).append(value)

    def refresh(self):
        for stack in self.stacks:
            status, _, body = self.api(stack, "/auth/login", method="POST",
                value={"email": stack["email"], "password": stack["password"]})
            require(status == 200, "phase-login")
            stack["token"] = json.loads(body)["access_token"]

    def read(self, stack):
        begin = time.monotonic()
        try:
            code = self.api(stack, "/categories", token=stack["token"])[0]
            return code == 200, time.monotonic() - begin
        except Exception:
            return False, time.monotonic() - begin

    def collector_metrics(self):
        try:
            status, _, body = request(self.obs["endpoints"]["self"], "/metrics", timeout=1)
            if status != 200:
                return None
            result = metrics(body.decode())
            for line in body.decode().splitlines():
                matched = re.fullmatch(r'(otelcol_exporter_[a-zA-Z0-9_]+)\{([^\n]*)\}\s+([0-9.eE+\-]+)', line)
                if not matched:
                    continue
                exporter = re.search(r'(?:^|,)exporter="(otlp_http/(?:traces|logs|metrics)|prometheusremotewrite)"(?:,|$)', matched[2])
                if exporter:
                    result[matched[1] + "|" + exporter[1]] = float(matched[3])
            return result
        except Exception:
            return None

    def grafana_query(self):
        value = {"queries": [{"refId": "A", "datasource": {"type": "prometheus", "uid": "capacity101"},
            "expr": "sum(http_server_requests)", "format": "time_series", "instant": True,
            "intervalMs": 1000, "maxDataPoints": 20}], "from": "now-1m", "to": "now"}
        status, _, raw = request(self.obs["endpoints"]["grafana"], "/api/ds/query", method="POST",
            body=json.dumps(value).encode(), headers={"Content-Type": "application/json", "Authorization": self.obs["auth"]}, timeout=3)
        require(status == 200, "actual-grafana-query")
        data = json.loads(raw)
        result = data["results"]["A"]
        require(not result.get("error"), "actual-grafana-result")
        values = [number for frame in result.get("frames", []) for series in frame.get("data", {}).get("values", [])[1:]
            for number in series if isinstance(number, (int, float))]
        require(all(math.isfinite(number) for number in values), "grafana-numeric-result")
        return any(number > 0 for number in values)

    def phase(self, name, seconds, rate=2, stopped=None):
        self.record["active_stage"] = name
        self.refresh()
        started = time.monotonic()
        started_unix = time.time()
        pending = {s["name"]: [] for s in self.stacks}
        outcomes = {s["name"]: [] for s in self.stacks}
        targets = {s["name"]: 0 for s in self.stacks}
        next_read = started
        next_sample = started
        self.sampler.begin(name)
        initial = self.collector_metrics()
        initial_store = stored_counts(self.obs["directory"])
        sample_future = None
        graph_futures = []
        next_graph = started + 2
        with ThreadPoolExecutor(max_workers=8) as pool, ThreadPoolExecutor(max_workers=1) as sample_pool, ThreadPoolExecutor(max_workers=1) as graph_pool:
            while time.monotonic() - started < seconds:
                require(time.monotonic() < self.deadline, "outer-work-deadline")
                now = time.monotonic()
                if now >= next_read:
                    for stack in self.stacks:
                        namekey = stack["name"]
                        completed = [f for f in pending[namekey] if f.done()]
                        outcomes[namekey].extend(f.result() for f in completed)
                        pending[namekey] = [f for f in pending[namekey] if not f.done()]
                        require(len(pending[namekey]) < 4, "load-concurrency-bound")
                        pending[namekey].append(pool.submit(self.read, stack))
                        targets[namekey] += 1
                    next_read += 1 / rate
                    require(now - next_read < .5, "load-generator-target-gap")
                if now >= next_sample:
                    if sample_future is not None:
                        require(sample_future.done(), "sampler-overlap")
                        sample_future.result()
                    sample_future = sample_pool.submit(self.sampler.sample, name, now - started, stopped)
                    next_sample += 3
                if stopped != "prometheus" and now >= next_graph:
                    require(not graph_futures or graph_futures[-1].done(), "grafana-query-concurrency-bound")
                    graph_futures.append(graph_pool.submit(self.grafana_query))
                    next_graph += 10
                time.sleep(.005)
            for key in pending:
                outcomes[key].extend(f.result(timeout=5) for f in pending[key])
            if sample_future is not None:
                sample_future.result(timeout=5)
            graph_values = [future.result(timeout=3) for future in graph_futures]
        elapsed = time.monotonic() - started
        summary = {"duration_seconds": elapsed, "target_seconds": seconds, "target_requests_per_second_per_environment": rate,
            "started_unix": started_unix, "finished_unix": time.time(),
            "concurrency_per_environment": 4, "collector_before": initial, "collector_after": self.collector_metrics(),
            "store_before": initial_store, "store_after": stored_counts(self.obs["directory"]), "environments": {}}
        summary["grafana"] = {"queries": len(graph_futures), "queries_with_actual_stored_value": sum(graph_values),
            "availability": "intentionally-unavailable" if stopped == "prometheus" else "queried"}
        for key, values in outcomes.items():
            delays = [duration for success, duration in values]
            passed = sum(success for success, duration in values)
            summary["environments"][key] = {"attempted": len(values), "success": passed, "errors": len(values) - passed,
                "p50_seconds": percentile(delays, .5), "p95_seconds": percentile(delays), "peak_seconds": max(delays, default=0),
                "achieved_requests_per_second": len(values) / seconds, "target_coverage": len(values) / (seconds * rate)}
            require(passed == len(values) and len(values) >= seconds * rate * .98, "actual-app-load-target")
            require(max(delays, default=0) <= 5, "request-deadline")
        self.record["phases"][name] = summary
        if "-disabled" in name:
            for row in self.record["samples"]:
                if row["phase"] == name:
                    self.check(name + "-no-sdk-export-work", all(not v["sdk_imported"] and v["sdk_worker_threads"] == 0
                        and not v.get("exports") for v in row["sdk_health"].values()))
        return summary

    def fresh(self, since):
        counts = stored_counts(self.obs["directory"])
        return all(counts[s]["newest_unix"] > since for s in SIGNALS)

    def recovery(self, target):
        since, began = time.time(), time.monotonic()
        self.compose(self.obs, "start", target, timeout=30)
        require(time.monotonic() - began <= 30, "destination-start-deadline")
        # Keep real application requests flowing and sample actual fields; stop
        # as soon as all three fresh receipts and actual Prom query have returned.
        index = 0
        while time.monotonic() - began < 120:
            self.phase("recovery-" + target + "-" + str(index), 4, rate=2)
            try:
                values = query(self.obs, "max(timestamp(http_server_requests))", request_timeout=2)
                prom_fresh = bool(values) and float(values[0]["value"][1]) > since
            except Exception:
                prom_fresh = False
            if self.fresh(since) and prom_fresh:
                require(time.monotonic() - began <= 120, "fresh-receipt-recovery-bound")
                self.record.setdefault("recoveries", {})[target] = {"fresh_three_signal_seconds": time.monotonic() - began,
                    "fresh_prometheus": True, "dropped_data_recovered": False}
                return
            index += 1
        raise Failure("fresh-three-signal-recovery-deadline")

    def privacy_requests(self):
        trace = uuid.uuid4().hex
        parent = uuid.uuid4().hex[:16]
        self.controlled = (trace, parent)
        for stack in self.stacks:
            self.check(stack["name"] + "-controlled-parent-request", self.api(stack, "/categories", token=stack["token"],
                headers={"traceparent": "00-" + trace + "-" + parent + "-01",
                    "baggage": "private=" + self.canaries[0], "tracestate": "private=" + self.canaries[1]})[0] == 200)
            self.check(stack["name"] + "-path-canary", self.api(stack, "/" + urllib.parse.quote(self.canaries[2], safe="") + "?private=" + urllib.parse.quote(self.canaries[3], safe=""),
                headers={"Authorization": self.canaries[4], "Cookie": self.canaries[5]})[0] == 404)
            self.check(stack["name"] + "-body-canary", self.api(stack, "/auth/login", method="POST",
                value={"email": self.canaries[6], "password": self.canaries[7]})[0] == 422)
            for value in ("bad", "0" * 9000):
                require(self.api(stack, "/auth/me", headers={"traceparent": value})[0] == 401, "malformed-context-safe")
        # Actual PostgreSQL transport failure through ordinary supported route.
        self.compose(self.stacks[0], "stop", "--timeout", "2", "db", timeout=10)
        self.check("controlled-real-postgres-failure-safe", self.api(self.stacks[0], "/categories", token=self.stacks[0]["token"])[0] == 500)
        self.compose(self.stacks[0], "start", "db", timeout=15)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if self.api(self.stacks[0], "/categories", token=self.stacks[0]["token"])[0] == 200:
                break
            time.sleep(.2)
        else:
            raise Failure("dependency-recovery")

    def audit(self):
        self.record["active_stage"] = "private-decoded-three-signal-audit"
        result = {}
        spans, span_environments, logs, exemplars = {}, {}, [], []
        routes = set(json.loads((ROOT / "openapi.yml").read_text())["paths"]) | {
            "unmatched", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
        environments = {signal: set() for signal in SIGNALS}
        for signal in SIGNALS:
            deliveries, unique, series = 0, set(), set()
            rawbytes = 0
            for document in decoded(self.obs["directory"], signal):
                require(time.monotonic() < self.deadline, "outer-audit-deadline")
                raw = json.dumps(document, sort_keys=True).encode()
                rawbytes += len(raw)
                for canary in self.canaries:
                    for form in (canary.encode(), urllib.parse.quote(canary, safe="").encode(), base64.b64encode(canary.encode()),
                                 canary.encode().hex().encode(), json.dumps(canary)[1:-1].encode()):
                        require(form not in raw, "private-canary-in-decoded-signal")
                for resource, scope, record in records(document, signal):
                    if signal != "metrics":
                        deliveries += 1
                        unique.add(identity(signal, resource, record))
                    attrs = attribute_map(resource.get("resource", {}).get("attributes", []))
                    require(set(attrs) == {"service.name", "service.version", "deployment.environment.name"}, "resource-allowlist")
                    require(attrs["service.name"] == "student-marketplace" and attrs["service.version"] == self.record["source"], "resource-explicit-build")
                    require(attrs["deployment.environment.name"] in {"development", "production"}, "resource-environment")
                    environments[signal].add(attrs["deployment.environment.name"])
                    require(scope.get("scope") == {"name": "marketplace.safe", "version": "1"}
                        and not scope.get("schemaUrl") and not resource.get("schemaUrl"), "scope-allowlist")
                    if signal == "traces":
                        require(record["name"] in {"http.request", "db.operation"} and not record.get("events") and not record.get("links"), "span-allowlist")
                        require(not record.get("status", {}).get("message"), "span-error-payload")
                        fields = attribute_map(record.get("attributes", []))
                        require(all(isinstance(value, str) and len(value) <= 128 for value in fields.values()), "span-attribute-value-bound")
                        if record["name"] == "http.request":
                            validate_http_attributes(fields, routes)
                        else:
                            require(set(fields) <= {"db.system.name", "db.operation.name", "outcome"}
                                and fields.get("db.system.name") == "postgresql"
                                and fields.get("db.operation.name") in {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK", "OTHER"}
                                and fields.get("outcome", "success") in {"success", "error"}, "db-allowlist")
                        spans[(record["traceId"], record["spanId"])] = record
                        span_environments[(record["traceId"], record["spanId"])] = attrs["deployment.environment.name"]
                    elif signal == "logs":
                        require(record.get("body") == {"stringValue": "http.request.completed"}
                            and not record.get("attributes"), "log-body-allowlist")
                        require(record.get("eventName") == "http.request.completed" and record.get("severityNumber") in {9, "SEVERITY_NUMBER_INFO"}, "log-event-severity-allowlist")
                        logs.append((record, attrs["deployment.environment.name"]))
                    else:
                        require(record["name"] in {"http.server.requests", "http.server.request.duration", "process.cpu.time", "process.memory.usage"}
                            and not record.get("description"), "metric-name-allowlist")
                        require(record.get("unit") == {"http.server.requests": "{request}", "http.server.request.duration": "s",
                            "process.cpu.time": "s", "process.memory.usage": "By"}[record["name"]], "metric-unit-allowlist")
                        for kind in ("sum", "gauge", "histogram", "exponentialHistogram"):
                            for point in record.get(kind, {}).get("dataPoints", []):
                                require(set(attribute_map(point.get("attributes", []))) <= {"http.route", "http.request.method", "http.response.status_class", "outcome"}, "metric-label-allowlist")
                                labels = attribute_map(point.get("attributes", []))
                                if record["name"].startswith("http."):
                                    validate_http_attributes(labels, routes)
                                else:
                                    require(not labels, "runtime-metric-labels")
                                    require(float(point.get("asInt", point.get("asDouble", 0))) > 0, "actual-positive-runtime-observation")
                                require(all(not e.get("filteredAttributes") for e in point.get("exemplars", [])), "exemplar-attribute-allowlist")
                                deliveries += 1
                                unique.add(digest(json.dumps([attrs, record["name"], point], sort_keys=True).encode()))
                                series.add(digest(json.dumps([attrs, record["name"], point.get("attributes", [])], sort_keys=True).encode()))
                                exemplars.extend(point.get("exemplars", []))
            require(deliveries > 0 and environments[signal] == {"development", "production"}, "actual-two-environment-signal-receipt")
            result[signal] = {"delivered_records": deliveries, "unique_records": len(unique), "duplicate_records": deliveries - len(unique),
                "decoded_bytes": rawbytes, "environments": sorted(environments[signal]), "canary_search_pass": True}
            if signal == "metrics":
                result[signal]["series_cardinality"] = len(series)
        correlated = sum((record.get("traceId"), record.get("spanId")) in spans for record, environment in logs)
        require(all(span_environments.get((record.get("traceId"), record.get("spanId")), environment) == environment
            for record, environment in logs), "concurrent-log-resource-context-isolation")
        children = [(key, span) for key, span in spans.items() if span["name"] == "db.operation"
            and (span["traceId"], span.get("parentSpanId")) in spans]
        require(children and all(span_environments[key] == span_environments[(span["traceId"], span["parentSpanId"])]
            for key, span in children), "concurrent-db-resource-context-isolation")
        self.check("actual-log-span-correlation", correlated > 0)
        normal_roots = sum(span["name"] == "http.request" and not span.get("parentSpanId") for span in spans.values())
        self.check("actual-normal-new-root-traces", normal_roots > 0)
        controlled, parent = self.controlled
        matches = [span for (trace, _), span in spans.items() if base64.b64decode(trace).hex() == controlled and span["name"] == "http.request"]
        self.check("actual-propagated-parent", bool(matches) and all(base64.b64decode(span["parentSpanId"]).hex() == parent for span in matches))
        self.check("actual-propagated-db-child", any(span["name"] == "db.operation" and any(span.get("parentSpanId") == match["spanId"] for match in matches) for span in spans.values()))
        resolved = sum((item.get("traceId"), item.get("spanId")) in spans for item in exemplars)
        self.check("actual-stored-metric-exemplar-correlation", resolved > 0)
        self.record["decoded_receipt"] = result
        self.record["correlation"] = {"log_span_resolved": correlated, "metric_exemplars": len(exemplars), "exemplar_span_resolved": resolved,
            "normal_root_requests": normal_roots, "resolved_db_parent_resources": len(children),
            "controlled_trace_sha256": digest(controlled.encode()), "raw_ids_published": False}
        # Collector and process diagnostics remain private; search before cleanup.
        for stack in [*self.stacks, self.obs]:
            raw = self.compose(stack, "logs", "--no-color", timeout=15).stdout.encode()
            require(all(form not in raw for canary in self.canaries for form in (
                canary.encode(), urllib.parse.quote(canary, safe="").encode(), base64.b64encode(canary.encode()),
                canary.encode().hex().encode(), json.dumps(canary)[1:-1].encode())), "private-canary-in-diagnostics")
        self.record["privacy"] = {"canaries": len(self.canaries), "decoded_three_signal_and_diagnostics_pass": True,
            "private_material_uploaded": False}

    def reconcile(self):
        totals = {signal: {"sdk_records_attempted": 0, "sdk_records_acked": 0, "sdk_failed_attempt_records": 0,
            "generated": 0, "sdk_queue_dropped": 0, "queued_at_shutdown": 0} for signal in SIGNALS}
        for app in self.record["app_shutdowns"]:
            if not app["enabled"]:
                continue
            for signal in SIGNALS:
                value = totals[signal]
                exports = app["exports"][signal]
                value["sdk_records_attempted"] += exports["records_attempted"]
                value["sdk_records_acked"] += exports["records_accepted"]
                value["sdk_failed_attempt_records"] += exports["records_failed"]
                if signal in {"traces", "logs"}:
                    value["generated"] += app["processor_observations"][signal]["emitted"]
                    value["sdk_queue_dropped"] += app["processor_observations"][signal]["queue_dropped"]
                    value["queued_at_shutdown"] += app["queued_on_shutdown"][signal]
                else:
                    value["generated"] += exports["records_attempted"]
        for signal in SIGNALS:
            value = totals[signal]
            value["post_collector_unique_stored"] = self.record["decoded_receipt"][signal]["unique_records"]
            value["retry_duplicate_deliveries"] = self.record["decoded_receipt"][signal]["duplicate_records"]
            value["missing_after_settle"] = value["generated"] - value["post_collector_unique_stored"]
            require(value["missing_after_settle"] >= 0, "unique-record-reconciliation")
            value["failed_attempts_are_unique_loss"] = False
        self.record["reconciliation"] = totals

    def projection(self):
        samples = self.record["samples"]
        seconds = max(1, samples[-1]["timestamp_unix"] - samples[0]["timestamp_unix"])
        first, last = samples[0]["storage"], samples[-1]["storage"]
        growth = max(0, sum(last.values()) - sum(first.values()))
        fixed = 1024 ** 3
        capacity = {"measurement_seconds": seconds, "total_observed_growth_bytes": growth,
            "conservative_daily_growth_bytes": math.ceil(growth / seconds * 86400 * 2),
            "fixed_WAL_compaction_and_backup_reserve_bytes": fixed,
            "daily_growth_safety_factor": 2, "oracle_memory_reserve_bytes": int(1.5 * 1024 ** 3),
            "oracle_cpu_reserve_fraction": .2, "arm_ocpu_fit": "unproven", "hosted_activation": "blocked",
            "limitations": "Short local ephemeral receipt; no production query or retention soak, no ARM/OCPU fit proof."}
        capacity["seven_day_projected_storage_bytes"] = capacity["conservative_daily_growth_bytes"] * 7 + fixed
        capacity["daily_projected_storage_bytes"] = capacity["conservative_daily_growth_bytes"] + fixed
        capacity["peak_service_memory_bytes"] = {name: max(row["services"].get(name, {}).get("memory_bytes", 0) for row in samples)
            for name in {key for row in samples for key in row["services"]}}
        capacity["peak_total_cpu_percent"] = max(row["aggregate_cpu_percent"] for row in samples)
        capacity["peak_total_memory_bytes"] = max(row["aggregate_memory_bytes"] for row in samples)
        capacity["peak_queues"] = {name: max(row.get("collector", {}).get(name, 0) for row in samples)
            for name in {key for row in samples for key in row.get("collector", {}) if "queue" in key}}
        self.record["capacity"] = capacity

    def main(self):
        setup = time.time() - float(os.environ.get("REHEARSAL103_SETUP_STARTED_UNIX", time.time()))
        self.record["ci_setup_seconds"] = setup
        require(0 <= setup <= 120, "ci-setup-budget")
        preparation_started = time.monotonic()
        self.record["active_stage"] = "provenance"
        self.provenance()
        self.record["input_sha256"].update({str(p.relative_to(ROOT)).replace("\\", "/"): digest(p.read_bytes())
            for pattern in ("backend/telemetry.py", "backend/otel_export.py", "backend/config.py", "backend/app.py", "tools/*103*.py", "ops/rehearsal103/*", ".github/workflows/rehearsal103.yml")
            for p in ROOT.glob(pattern) if p.is_file()})
        self.certificates()
        self.images()
        self.observability()
        self.stacks = [self.stack(name) for name in ("dev", "prod")]
        for stack in self.stacks:
            self.up(stack)
            self.journey(stack)
        self.record["preparation_seconds"] = time.monotonic() - preparation_started
        require(self.record["preparation_seconds"] <= 240, "preparation-budget")
        self.record["phase_plan"] = PLANS[self.part]
        self.record["phase_plan_sha256"] = digest(json.dumps(PLANS[self.part], sort_keys=True).encode())
        self.record["phase_host_fingerprint"] = digest(json.dumps(self.record["host"], sort_keys=True).encode())
        self.record["observer_cost"] = "Same fixture wrapper enabled/disabled; sampling/observation overhead included, not separately subtracted. Never combine CPU/RAM observations across jobs."
        self.sampler = Sampler(self)
        if self.part == "capacity":
            for pair in range(3):
                for enabled in ((False, True) if pair % 2 == 0 else (True, False)):
                    self.telemetry(enabled)
                    self.phase("pair-" + str(pair) + ("-enabled" if enabled else "-disabled"), 120)
            self.telemetry(True)
            self.phase("enabled-load", 300)
        else:
            self.telemetry(True)
            self.phase("outage-job-healthy-baseline", 15)
        privacy_started = time.monotonic()
        self.privacy_requests()
        require(time.monotonic() - privacy_started <= 20, "privacy-fixture-budget")
        if self.part == "functional":
            self.compose(self.obs, "pause", "collector", timeout=10)
            self.phase("sdk-backpressure-collector-paused", 12, rate=64, stopped="collector")
            self.compose(self.obs, "unpause", "collector", timeout=10)
            saturation = [row for row in self.record["samples"] if row["phase"] == "sdk-backpressure-collector-paused"]
            self.check("actual-sdk-queue-saturation", any(v["processor_observations"][s]["queue_dropped"] > 0
                for row in saturation for v in row["sdk_health"].values() for s in ("traces", "logs")))
        if self.part in {"functional", "capacity"}:
            for target in PLANS[self.part]["outages"]:
                before = self.collector_metrics()
                self.compose(self.obs, "stop", "--timeout", "3", target, timeout=10)
                phase = self.phase("outage-" + target, 60, rate=32 if target != "prometheus" else 8, stopped=target)
                self.recovery(target)
                after = self.collector_metrics()
                self.record.setdefault("outages", {})[target] = {"seconds": 60, "before": before, "after": after,
                    "requests_successful": all(v["errors"] == 0 for v in phase["environments"].values())}
                if target != "collector":
                    component = "prometheusremotewrite" if target == "prometheus" else "otlp_http/" + target
                    snapshots = [row["collector"] for row in self.record["samples"] if row["phase"] == "outage-" + target]
                    sizes = [value for row in snapshots for key, value in row.items() if "queue_size|" + component == key.removeprefix("otelcol_exporter_")]
                    # Exact queue labels/version names must be observed, never
                    # replace absent counters with an invented zero.
                    self.check("actual-downstream-queue-saturated-" + target, bool(sizes) and max(sizes) >= 2)
        self.phase("settle", 8)
        for stack in self.stacks:
            self.collect_shutdown(stack)
        # Final SDK flush must traverse Collector before offline unique counts.
        time.sleep(3)
        self.audit()
        self.reconcile()
        self.projection()
        self.record["result"] = "PASS"


class Sampler:
    def __init__(self, controller):
        self.r = controller
        self.previous = {}
        self.previous_cpu = host_cpu()
        self.previous_generator = (time.monotonic(), time.process_time())
        self.bad = {}

    def begin(self, name):
        self.previous = {}
        self.previous_cpu = host_cpu()
        self.previous_generator = (time.monotonic(), time.process_time() + os.times().children_user + os.times().children_system)

    def sustained(self, key, bad):
        now = time.monotonic()
        if not bad:
            self.bad.pop(key, None)
        else:
            self.bad.setdefault(key, now)
            require(now - self.bad[key] < 30, key)

    def storage(self):
        result = {}
        script = "import os,json;print(json.dumps({p:sum(os.stat(os.path.join(r,f)).st_size for r,d,fs in os.walk(p) for f in fs) for p in ['/metrics','/grafana']}))"
        values = json.loads(self.r.compose(self.r.obs, "exec", "-T", "control", "python", "-c", script, timeout=3).stdout)
        result.update({name: value for name, value in values.items()})
        for signal, value in stored_counts(self.r.obs["directory"]).items():
            result[signal] = value["bytes"]
        return result, (time.monotonic(), time.time())

    def sdk_health(self, name):
        status, _, raw = request(self.r.obs["endpoints"][name + "-sdk"], "/health", timeout=1)
        require(status == 200, "local-sdk-health")
        return json.loads(raw), (time.monotonic(), time.time())

    def receiver_health(self, signal):
        status, _, raw = request(self.r.obs["endpoints"][signal], "/health", timeout=1)
        require(status == 200, "local-receiver-health")
        value = json.loads(raw)
        require(set(value) == {"accepted", "refused", "evicted_files"}
            and all(isinstance(v, int) and v >= 0 for v in value.values()), "receiver-health-schema")
        return value, (time.monotonic(), time.time())

    def sample(self, phase, elapsed, stopped):
        r = self.r
        times = {}
        row = {"phase": phase, "elapsed_seconds": elapsed, "timestamp_unix": time.time(), "services": {}}
        begin = time.monotonic()
        def stamp(*keys):
            instant = (time.monotonic(), time.time())
            for key in keys:
                times[key] = instant
        with ThreadPoolExecutor(max_workers=8) as pool:
            storage = pool.submit(self.storage)
            app_times = {s["name"]: {} for s in r.stacks}
            app_futures = {s["name"]: pool.submit(app_disk, r, s, app_times[s["name"]]) for s in r.stacks}
            sdk_futures = {s["name"]: pool.submit(self.sdk_health, s["name"]) for s in r.stacks}
            receiver_futures = {signal: pool.submit(self.receiver_health, signal) for signal in SIGNALS if signal != stopped}
            ids = []
            for stack in [*r.stacks, r.obs]:
                ids.extend(r.compose(stack, "ps", "-aq").stdout.split())
            values = json.loads(r.run(["docker", "inspect", *ids], timeout=3).stdout)
            running = []
            byname = {}
            for value in values:
                labels = value["Config"]["Labels"]
                require(labels.get(LABEL) == r.owner, "sample-ownership")
                service = labels["com.docker.compose.service"]
                project = labels["com.docker.compose.project"]
                require(not value["State"].get("OOMKilled") and value["RestartCount"] == 0, "oom-or-unexpected-restart")
                if service in {"migrate", "uploads-init"}:
                    require(value["State"]["ExitCode"] == 0, "one-shot-state")
                    continue
                require(value["State"]["Running"] or service == stopped, "unexpected-service-exit")
                expected_networks = {project + "_default"}
                if service in {"proxy", "control"}:
                    expected_networks.add(project + "_ingress")
                if service == "app":
                    expected_networks.add(r.obs["project"] + "_" + project.rsplit("-", 1)[-1] + "telemetry")
                if service in {"collector", "control"}:
                    expected_networks.update(r.obs["project"] + "_" + name + "telemetry" for name in ("dev", "prod"))
                require(set(value["NetworkSettings"]["Networks"]) == expected_networks, "exact-owned-network-membership")
                if value["State"]["Running"]:
                    running.append(value["Id"])
                    byname[value["Name"].lstrip("/")] = value
            raw = r.run(["docker", "stats", "--no-stream", "--format", "{{json .}}", *running], timeout=3).stdout
            for line in raw.splitlines():
                value = json.loads(line)
                info = byname[value["Name"]]
                labels = info["Config"]["Labels"]
                service = labels["com.docker.compose.service"]
                project = labels["com.docker.compose.project"]
                name = project.rsplit("-", 1)[-1] + "/" + service
                memory = bytes_value(value["MemUsage"].split("/")[0])
                cap = 128 * 1024 ** 2 if service in SIGNALS else CAPS[service][1] * 1024 ** 2
                row["services"][name] = {"cpu_percent": float(value["CPUPerc"].rstrip("%")), "memory_bytes": memory, "cap_bytes": cap}
                stamp(name + "/cpu", name + "/memory")
                self.sustained("memory-stop-" + name, memory > .85 * cap)
            row["aggregate_cpu_percent"] = sum(v["cpu_percent"] for v in row["services"].values())
            row["aggregate_memory_bytes"] = sum(v["memory_bytes"] for v in row["services"].values())
            stamp("aggregate_cpu_percent", "aggregate_memory_bytes")
            self.sustained("aggregate-cpu-stop", row["aggregate_cpu_percent"] > os.cpu_count() * 80)
            row["storage"], instant = storage.result(timeout=3)
            for name in row["storage"]:
                times["disk/" + name] = instant
            row["app_storage"] = {name: future.result(timeout=3) for name, future in app_futures.items()}
            for value in app_times.values():
                times.update(value)
            row["sdk_health"] = {}
            for name, future in sdk_futures.items():
                row["sdk_health"][name], instant = future.result(timeout=1)
                times[name + "/sdk-health"] = instant
            row["receiver_health"] = {signal: None for signal in SIGNALS}
            for signal, future in receiver_futures.items():
                row["receiver_health"][signal], instant = future.result(timeout=1)
                times[signal + "/receiver-health"] = instant
        row["collector"] = r.collector_metrics() if stopped != "collector" else None
        if stopped != "collector":
            require(row["collector"] is not None, "collector-self-metrics")
            row["collector"] = {key: value for key, value in row["collector"].items() if any(word in key for word in ("queue", "accepted", "refused", "sent_", "send_failed", "enqueue_failed"))}
            for component in ("otlp_http/traces", "otlp_http/logs", "otlp_http/metrics", "prometheusremotewrite"):
                capacities = [value for key, value in row["collector"].items() if key.endswith("queue_capacity|" + component)]
                sizes = [value for key, value in row["collector"].items() if key.endswith("queue_size|" + component)]
                require(len(capacities) == len(sizes) == 1 and capacities[0] == 2 and 0 <= sizes[0] <= capacities[0], "actual-exporter-queue-bound")
            stamp("collector-queues-counters")
        else:
            row["collector"] = {}
        for stack in r.stacks:
            healthy = request(stack["origin"], "/health/ready", context=r.context, timeout=5)[0] == 200
            row[stack["name"] + "_ready"] = healthy
            self.sustained("app-unhealthy-" + stack["name"], not healthy)
        stamp("readiness")
        disk = shutil.disk_usage(r.private)
        row["disk_free_bytes"] = disk.free
        require(disk.free >= max(4 * 1024 ** 3, .2 * disk.total), "disk-stop")
        current = host_cpu()
        delta = current[0] - self.previous_cpu[0]
        row["host_cpu_percent"] = 100 * os.cpu_count() * (1 - (current[1] - self.previous_cpu[1]) / delta) if delta else 0
        self.previous_cpu = current
        content = Path("/proc/meminfo").read_text()
        row["host_memory_bytes"] = (int(re.search(r"MemTotal:\s+(\d+)", content)[1]) - int(re.search(r"MemAvailable:\s+(\d+)", content)[1])) * 1024
        generator = (time.monotonic(), time.process_time() + os.times().children_user + os.times().children_system)
        row["generator_cpu_percent"] = 100 * (generator[1] - self.previous_generator[1]) / max(.001, generator[0] - self.previous_generator[0])
        self.previous_generator = generator
        from backend.telemetry import resident_bytes
        row["generator_memory_bytes"] = resident_bytes()
        stamp("host-cpu", "host-memory", "generator-cpu", "generator-memory", "free-disk")
        gaps = {key: instant[0] - self.previous[key] for key, instant in times.items() if key in self.previous}
        self.previous.update({key: instant[0] for key, instant in times.items()})
        row["field_timestamps_unix"] = {key: instant[1] for key, instant in times.items()}
        row["field_max_gap_seconds"] = max(gaps.values(), default=0)
        row["sample_collection_seconds"] = time.monotonic() - begin
        r.record["samples"].append(row)
        require(row["field_max_gap_seconds"] <= 5, "actual-field-sample-gap")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", required=True, choices=["issue-103-synthetic-only"])
    parser.add_argument("--part", choices=sorted(PLANS), default="preflight")
    args = parser.parse_args()
    require(sys.platform == "linux", "linux-required")
    safe = ROOT / "rehearsal103-safe"
    require(not safe.is_symlink() and (not safe.exists() or not any(safe.iterdir())), "safe-output-not-empty")
    safe.mkdir(exist_ok=True)
    controller = Controller(args.part)
    try:
        controller.main()
    except Failure as error:
        controller.record["failure_stage"] = str(error)
    except Exception as error:
        controller.record["failure_stage"] = "controller-error"
        controller.record.update(failure_metadata(error))
        import traceback
        for frame in traceback.extract_tb(error.__traceback__):
            if Path(frame.filename).resolve() == Path(__file__).resolve():
                controller.record["failure_location"] = {"file": "tools/rehearsal103.py", "function": frame.name, "line": frame.lineno}
    finally:
        controller.cleanup()
        controller.record["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (safe / "summary.json").write_text(json.dumps(controller.record, indent=2) + "\n")
    print(json.dumps({key: controller.record[key] for key in ("result", "cleanup")}))
    return 0 if controller.record["result"] == "PASS" else 1


if __name__ == "__main__":
    from tools.rehearsal103 import main as canonical_main
    try:
        raise SystemExit(canonical_main())
    except Failure:
        print("Rehearsal invocation refused")
        raise SystemExit(1)
