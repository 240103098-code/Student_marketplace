"""Bounded explicit OTLP/HTTP adapter using official SDK exporter interfaces.

Official HTTP constructors merge ambient credentials and parse private headers
before an outgoing Session hook can sanitize them (#116). This adapter never
consults those constructors/environment. Official protobuf encoders retain wire
compatibility; responses/exceptions are never interpolated into diagnostics.
"""
import http.client
import io
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit


class DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline
    def readable(self):
        return True
    def readinto(self, target):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.sock.settimeout(min(.5, remaining))
        return self.sock.recv_into(target)


class DeadlineSocket:
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline
    def __getattr__(self, name):
        return getattr(self.sock, name)
    def makefile(self, mode, buffering=None):
        return io.BufferedReader(DeadlineReader(self.sock, self.deadline))


class Transport:
    def __init__(self, endpoint, signal, resolver=None):
        self.origin = urlsplit(endpoint)
        self.signal = signal
        self.resolver = resolver or Resolver(self.origin.hostname)
        self.closed = False
        self.lock = threading.Lock()
        self.counters = dict(batches_attempted=0, records_attempted=0, records_accepted=0,
            records_failed=0, oversize_records=0, transport_failures=0)
    def send(self, payload, count):
        with self.lock:
            self.counters["batches_attempted"] += 1
            self.counters["records_attempted"] += count
        if self.closed or len(payload) > 65536:
            with self.lock:
                self.counters["records_failed"] += count
                self.counters["oversize_records"] += count if len(payload) > 65536 else 0
            return False
        connection = None
        success = False
        try:
            deadline = time.monotonic() + 1
            parsed = self.origin
            address = self.resolver.resolve(deadline)
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            class Connection(http.client.HTTPConnection):
                def connect(inner):
                    inner.sock = socket.socket(family, socket.SOCK_STREAM)
                    inner.sock.settimeout(min(.2, max(.001, deadline - time.monotonic())))
                    inner.sock.connect((address, parsed.port or (443 if parsed.scheme == "https" else 80)))
                    if parsed.scheme == "https":
                        inner.sock = ssl.create_default_context().wrap_socket(inner.sock, server_hostname=parsed.hostname)
            connection = Connection(parsed.hostname, parsed.port, timeout=.2)
            connection.connect()
            connection.sock = DeadlineSocket(connection.sock, deadline)
            connection.request("POST", "/v1/" + self.signal, payload,
                {"Content-Type": "application/x-protobuf", "Connection": "close"})
            response = connection.getresponse()
            # No redirects, retries or response text diagnostics. Bound bytes
            # and absolute socket read deadline, including trickled headers.
            body = response.read(4097)
            success = response.status == 200 and len(body) <= 4096
            if success and body:
                from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
                from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse
                from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceResponse
                cls = {"traces": ExportTraceServiceResponse, "logs": ExportLogsServiceResponse,
                    "metrics": ExportMetricsServiceResponse}[self.signal]
                value = cls()
                value.ParseFromString(body)
                rejected = getattr(value.partial_success, {"traces": "rejected_spans", "logs": "rejected_log_records",
                    "metrics": "rejected_data_points"}[self.signal])
                success = rejected == 0
        except Exception:
            # A fixed safe local counter is the complete failure diagnostic.
            success = False
        finally:
            if connection is not None:
                connection.close()
        with self.lock:
            self.counters["records_accepted" if success else "records_failed"] += count
            if not success:
                self.counters["transport_failures"] += 1
        return success
    def shutdown(self):
        self.closed = True


class Resolver:
    """One bounded app-owned cached DNS lookup; no uninterruptible DNS worker."""
    def __init__(self, hostname):
        self.hostname = hostname
        self.lock = threading.Lock()
        self.value, self.expires = None, 0
    def resolve(self, deadline):
        try:
            return str(ipaddress.ip_address(self.hostname))
        except ValueError:
            pass
        if self.hostname == "localhost":
            return "127.0.0.1"
        if not self.lock.acquire(timeout=max(.001, deadline - time.monotonic())):
            raise TimeoutError()
        try:
            if time.monotonic() < self.expires:
                if self.value is None:
                    raise TimeoutError()
                return self.value
            # Only fixed collector is a nonliteral hostname permitted by config.
            script = "import socket,json;print(json.dumps([v[4][0] for v in socket.getaddrinfo('collector',None,socket.AF_INET,socket.SOCK_STREAM)]))"
            env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "LANG") if key in os.environ}
            self.value, self.expires = None, time.monotonic() + 1
            value = subprocess.run([sys.executable, "-c", script], capture_output=True, env=env,
                timeout=min(.3, max(.001, deadline - time.monotonic())), check=True)
            addresses = json.loads(value.stdout[:4096])
            address = ipaddress.ip_address(addresses[0])
            if not address.is_private:
                raise ValueError()
            self.value, self.expires = str(address), time.monotonic() + 60
            return self.value
        finally:
            self.lock.release()


def exporters(endpoint):
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.sdk._logs.export import LogRecordExporter, LogRecordExportResult
    from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.exporter.otlp.proto.common._log_encoder import encode_logs
    from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
    resolver = Resolver(urlsplit(endpoint).hostname)
    class Spans(SpanExporter):
        def __init__(self):
            self.transport = Transport(endpoint, "traces", resolver)
        def export(self, batch):
            return SpanExportResult.SUCCESS if self.transport.send(encode_spans(batch).SerializeToString(), len(batch)) else SpanExportResult.FAILURE
        def shutdown(self):
            self.transport.shutdown()
    class Logs(LogRecordExporter):
        def __init__(self):
            self.transport = Transport(endpoint, "logs", resolver)
        def export(self, batch):
            return LogRecordExportResult.SUCCESS if self.transport.send(encode_logs(batch).SerializeToString(), len(batch)) else LogRecordExportResult.FAILURE
        def shutdown(self):
            self.transport.shutdown()
        def force_flush(self, timeout_millis=30000):
            return True
    class Metrics(MetricExporter):
        def __init__(self):
            super().__init__()
            self.transport = Transport(endpoint, "metrics", resolver)
        def export(self, data, timeout_millis=10000, **kwargs):
            count = sum(len(metric.data.data_points) for resource in data.resource_metrics
                for scope in resource.scope_metrics for metric in scope.metrics)
            return MetricExportResult.SUCCESS if self.transport.send(encode_metrics(data).SerializeToString(), count) else MetricExportResult.FAILURE
        def force_flush(self, timeout_millis=10000):
            return True
        def shutdown(self, timeout_millis=30000, **kwargs):
            self.transport.shutdown()
    return Spans(), Logs(), Metrics()
