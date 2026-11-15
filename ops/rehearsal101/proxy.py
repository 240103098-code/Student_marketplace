"""Disposable fixture HTTPS termination; no forwarded-header trust or request logging."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def forward(self):
        # Only the application's bounded JSON/image requests, never arbitrary upstreams.
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 <= size <= 6 * 1024 * 1024:
            self.send_error(413)
            return
        connection = http.client.HTTPConnection('app', 8000, timeout=12)
        try:
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ('connection', 'transfer-encoding', 'proxy-authorization')}
            connection.request(self.command, self.path, self.rfile.read(size), headers)
            response = connection.getresponse()
            body = response.read(8 * 1024 * 1024)
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in ('connection', 'transfer-encoding', 'content-length', 'server', 'date'):
                    self.send_header(key, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.close_connection = True
        finally:
            connection.close()

    do_GET = do_POST = do_PATCH = do_DELETE = do_OPTIONS = forward


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', 8443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('/tls/server.pem', '/tls/server.key')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
