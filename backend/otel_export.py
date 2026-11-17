"""Bounded explicit OTLP/HTTP adapter using official SDK exporter interfaces.

Official HTTP constructors merge ambient credentials and parse private headers
before an outgoing Session hook can sanitize them (#116). This adapter never
consults those constructors/environment. Official protobuf encoders retain wire
compatibility; responses/exceptions are never interpolated into diagnostics.
"""
import http.client
import io
import ssl
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
    def __init__(self, endpoint, signal):
        self.origin = urlsplit(endpoint)
        self.signal = signal
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
            if parsed.scheme == "https":
                # Default verified system trust only; never OTEL cert/key env.
                connection = http.client.HTTPSConnection(parsed.hostname, parsed.port, timeout=.2,
                    context=ssl.create_default_context())
            else:
                connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=.2)
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


def exporters(endpoint):
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.sdk._logs.export import LogRecordExporter, LogRecordExportResult
    from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.exporter.otlp.proto.common._log_encoder import encode_logs
    from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
    class Spans(SpanExporter):
        def __init__(self):
            self.transport = Transport(endpoint, "traces")
        def export(self, batch):
            return SpanExportResult.SUCCESS if self.transport.send(encode_spans(batch).SerializeToString(), len(batch)) else SpanExportResult.FAILURE
        def shutdown(self):
            self.transport.shutdown()
    class Logs(LogRecordExporter):
        def __init__(self):
            self.transport = Transport(endpoint, "logs")
        def export(self, batch):
            return LogRecordExportResult.SUCCESS if self.transport.send(encode_logs(batch).SerializeToString(), len(batch)) else LogRecordExportResult.FAILURE
        def shutdown(self):
            self.transport.shutdown()
        def force_flush(self, timeout_millis=30000):
            return True
    class Metrics(MetricExporter):
        def __init__(self):
            super().__init__()
            self.transport = Transport(endpoint, "metrics")
        def export(self, data, timeout_millis=10000, **kwargs):
            count = sum(len(metric.data.data_points) for resource in data.resource_metrics
                for scope in resource.scope_metrics for metric in scope.metrics)
            return MetricExportResult.SUCCESS if self.transport.send(encode_metrics(data).SerializeToString(), count) else MetricExportResult.FAILURE
        def force_flush(self, timeout_millis=10000):
            return True
        def shutdown(self, timeout_millis=30000, **kwargs):
            self.transport.shutdown()
    return Spans(), Logs(), Metrics()
