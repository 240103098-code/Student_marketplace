"""Private bounded actual OTLP protobuf receipt for disposable #103 rehearsal.

One process/directory per signal permits independent destination failures. No raw
record is returned over HTTP. Decoded files are private and never CI artifacts.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import time

REQUEST_LIMIT = 65536
STORE_LIMIT = 128 * 1024 * 1024
RECORD_LIMIT = 2048
RETENTION_SECONDS = 24 * 3600
FILE_LIMIT = 4096


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
        self.sequence = time.time_ns()
        self.accepted = self.refused = self.evicted = 0

    def append(self, encoded, count):
        now = time.time()
        files = sorted(self.directory.glob("*.json"))
        sizes = [(path, path.stat().st_size) for path in files]
        size = sum(length for path, length in sizes)
        while sizes and (size + len(encoded) > self.limit or len(sizes) >= FILE_LIMIT
                         or now - sizes[0][0].stat().st_mtime >= RETENTION_SECONDS):
            path, length = sizes.pop(0)
            if path.is_symlink() or path.parent != self.directory:
                raise ValueError("private-file")
            path.unlink()
            size -= length
            self.evicted += 1
        if len(encoded) > self.limit:
            self.refused += count
            return False
        self.sequence += 1
        path = self.directory / (str(self.sequence) + ".json")
        with path.open("xb") as target:
            path.chmod(0o600)
            target.write(encoded)
        self.accepted += count
        return True


def server(signal, directory, port=4318):
    store = Store(directory)
    class Handler(BaseHTTPRequestHandler):
        timeout = 2
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            body = json.dumps({"accepted": store.accepted, "refused": store.refused, "evicted_files": store.evicted}).encode()
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
                    self.send_error(507)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:
                # No diagnostic may expose untrusted text/decoding exceptions.
                store.refused += 1
                self.send_error(400)
                self.close_connection = True
    instance = HTTPServer(("0.0.0.0", port), Handler)
    instance.timeout = 2
    instance.serve_forever(poll_interval=.2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", choices=["traces", "logs", "metrics"], required=True)
    parser.add_argument("--private-directory", required=True)
    parser.add_argument("--port", type=int, default=4318)
    args = parser.parse_args()
    server(args.signal, args.private_directory, args.port)
