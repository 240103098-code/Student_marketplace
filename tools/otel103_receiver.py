"""Private bounded actual OTLP protobuf receipt for disposable #103 rehearsal.

One process/directory per signal permits independent destination failures. No raw
record is returned over HTTP. Decoded files are private and never CI artifacts.
"""
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
from pathlib import Path
import time

REQUEST_LIMIT = 65536
STORE_LIMIT = 128 * 1024 * 1024
RECORD_LIMIT = 2048
RETENTION_SECONDS = 24 * 3600
FILE_LIMIT = 16384


def decode(signal, payload):
    from google.protobuf.json_format import MessageToDict
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
    classes = {"traces": ExportTraceServiceRequest, "logs": ExportLogsServiceRequest, "metrics": ExportMetricsServiceRequest}
    if len(payload) > REQUEST_LIMIT:
        raise ValueError("request-bound")
    message = classes[signal]()
    message.ParseFromString(payload)
    count = 0
    if signal == "traces":
        count = sum(len(scope.spans) for resource in message.resource_spans for scope in resource.scope_spans)
    elif signal == "logs":
        count = sum(len(scope.log_records) for resource in message.resource_logs for scope in resource.scope_logs)
    else:
        for resource in message.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    data = getattr(metric, metric.WhichOneof("data"))
                    count += len(data.data_points)
    if count > RECORD_LIMIT:
        raise ValueError("record-bound")
    # JSON conversion is bounded by the 64KiB uncompressed protobuf cap.
    document = MessageToDict(message)
    encoded = json.dumps(document, separators=(",", ":")).encode()
    if len(encoded) > REQUEST_LIMIT * 8:
        raise ValueError("decoded-bound")
    return encoded, count


class Store:
    def __init__(self, directory, limit=STORE_LIMIT):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise ValueError("private-directory")
        self.limit = min(limit, STORE_LIMIT)
        self.block_size = os.statvfs(self.directory).f_frsize if hasattr(os, "statvfs") else 1
        self.sequence = time.time_ns()
        self.accepted = self.refused_requests = self.refused_records = self.unknown_refused_requests = self.evicted = 0
        stats = self.directory / ".receipt-stats"
        if stats.exists():
            if stats.is_symlink() or stats.stat().st_size > 4096:
                raise ValueError("stats-bound")
            value = json.loads(stats.read_bytes())
            if set(value) != {"accepted", "refused_requests", "refused_records", "unknown_refused_requests", "evicted_files"} or not all(
                isinstance(v, int) and v >= 0 for v in value.values()):
                raise ValueError("stats-schema")
            self.accepted = value["accepted"]
            self.refused_requests = value["refused_requests"]
            self.refused_records = value["refused_records"]
            self.unknown_refused_requests = value["unknown_refused_requests"]
            self.evicted = value["evicted_files"]
        self.files = deque()
        self.bytes = 0
        for path in sorted(self.directory.glob("*.json")):
            if path.is_symlink():
                raise ValueError("private-file")
            info = path.stat()
            size = info.st_blocks * 512 if hasattr(info, "st_blocks") else info.st_size
            self.files.append((path, size, path.stat().st_mtime))
            self.bytes += size

    def counters(self):
        return {"accepted": self.accepted, "refused_requests": self.refused_requests,
            "refused_records": self.refused_records, "unknown_refused_requests": self.unknown_refused_requests,
            "evicted_files": self.evicted}

    def persist(self):
        path, temporary = self.directory / ".receipt-stats", self.directory / ".receipt-stats.tmp"
        if path.is_symlink() or temporary.is_symlink():
            raise ValueError("stats-path")
        with temporary.open("w") as target:
            temporary.chmod(0o600)
            target.write(json.dumps(self.counters()))
        temporary.replace(path)

    def refuse(self, count=None):
        self.refused_requests += 1
        if count is None:
            self.unknown_refused_requests += 1
        else:
            self.refused_records += count
        self.persist()

    def append(self, encoded, count):
        now = time.time()
        needed = math.ceil(len(encoded) / self.block_size) * self.block_size
        directory_info = self.directory.stat()
        directory_cost = directory_info.st_blocks * 512 if hasattr(directory_info, "st_blocks") else 0
        if needed + directory_cost > self.limit:
            self.refuse(count)
            return False
        while self.files and (self.bytes + needed + directory_cost > self.limit or len(self.files) >= FILE_LIMIT
                         or now - self.files[0][2] >= RETENTION_SECONDS):
            path, length, timestamp = self.files.popleft()
            if path.is_symlink() or path.parent != self.directory:
                raise ValueError("private-file")
            path.unlink()
            self.bytes -= length
            self.evicted += 1
        self.sequence += 1
        path = self.directory / (str(self.sequence) + ".json")
        with path.open("xb") as target:
            path.chmod(0o600)
            target.write(encoded)
        info = path.stat()
        allocated = info.st_blocks * 512 if hasattr(info, "st_blocks") else info.st_size
        self.files.append((path, allocated, now))
        self.bytes += allocated
        directory_info = self.directory.stat()
        directory_cost = directory_info.st_blocks * 512 if hasattr(directory_info, "st_blocks") else 0
        while self.files and self.bytes + directory_cost > self.limit:
            old, size, timestamp = self.files.popleft()
            old.unlink()
            self.bytes -= size
            self.evicted += 1
        self.accepted += count
        self.persist()
        return True


def make_server(signal, directory, port=4318, host="0.0.0.0"):
    # Reserve an atomic stats replacement's old+new blocks within128MiB.
    store = Store(directory, STORE_LIMIT - 8192)
    class Handler(BaseHTTPRequestHandler):
        timeout = 2
        def setup(self):
            from backend.otel_export import DeadlineSocket
            self.request = DeadlineSocket(self.request, time.monotonic() + 2)
            super().setup()
        def log_message(self, *args):
            pass
        def send_error(self, code, *ignored, **kwargs):
            if not getattr(self, "_refusal_recorded", False):
                store.refuse()
                self._refusal_recorded = True
            body = b"Receipt unavailable."
            self.send_response(code, "Receipt unavailable")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            body = json.dumps(store.counters()).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            try:
                if (self.path != "/v1/" + signal or self.headers.get("Content-Encoding", "identity") != "identity"
                    or self.headers.get("Content-Type") != "application/x-protobuf"
                    or self.headers.get("Transfer-Encoding") is not None):
                    raise ValueError("protocol")
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 <= length <= REQUEST_LIMIT:
                    raise ValueError("request-bound")
                payload = self.rfile.read(length)
                if len(payload) != length:
                    raise ValueError("incomplete-request")
                encoded, count = decode(signal, payload)
                if not store.append(encoded, count):
                    self._refusal_recorded = True
                    self.send_error(507)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:
                # No diagnostic may expose untrusted text/decoding exceptions.
                store.refuse()
                self._refusal_recorded = True
                self.send_error(400)
                self.close_connection = True
    class Server(HTTPServer):
        def handle_error(self, *ignored):
            pass
    instance = Server((host, port), Handler)
    instance.timeout = 2
    return instance


def server(signal, directory, port=4318):
    instance = make_server(signal, directory, port)
    instance.serve_forever(poll_interval=.2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", choices=["traces", "logs", "metrics"], required=True)
    parser.add_argument("--private-directory", required=True)
    parser.add_argument("--port", type=int, default=4318)
    args = parser.parse_args()
    server(args.signal, args.private_directory, args.port)
