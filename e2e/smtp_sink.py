"""Private test-only STARTTLS/AUTH mail sink. No listener or dependency in app image."""
import base64
from email import policy
from email.parser import BytesParser
import hmac
import json
import os
from pathlib import Path
import re
import socketserver
import ssl
import uuid

ROOT = Path(os.environ.get('E2E_SMTP_ROOT', '/fixture'))
CONFIG = json.loads((ROOT / 'smtp.json').read_text())

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        secure = authenticated = False
        recipient = None
        self.wfile.write(b'220 smtp.test ready\r\n')
        while True:
            line = self.rfile.readline(4096)
            if not line: return
            parts = line.decode('ascii', errors='replace').strip().split(' ', 1)
            verb, arg = parts[0].upper(), parts[1] if len(parts) > 1 else ''
            reply = b'500 unsupported\r\n'
            if verb in ('EHLO', 'HELO'):
                reply = b'250-smtp.test\r\n' + (b'250 AUTH PLAIN\r\n' if secure else b'250 STARTTLS\r\n')
            elif verb == 'STARTTLS' and not secure:
                self.wfile.write(b'220 begin TLS\r\n'); self.wfile.flush()
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(ROOT/'server.pem', ROOT/'server.key')
                self.connection = context.wrap_socket(self.connection, server_side=True)
                self.rfile = self.connection.makefile('rb'); self.wfile = self.connection.makefile('wb', buffering=0)
                secure = True; continue
            elif verb == 'AUTH' and secure:
                try:
                    scheme, payload = arg.split(' ', 1)
                    values = base64.b64decode(payload, validate=True).split(b'\0')
                    authenticated = scheme == 'PLAIN' and len(values) == 3 and hmac.compare_digest(values[1].decode(), CONFIG['username']) and hmac.compare_digest(values[2].decode(), CONFIG['password'])
                except Exception: authenticated = False
                reply = b'235 authenticated\r\n' if authenticated else b'535 rejected\r\n'
            elif verb == 'MAIL' and authenticated:
                recipient = None; reply = b'250 sender accepted\r\n'
            elif verb == 'RCPT' and authenticated:
                match = re.fullmatch(r'TO:<([a-z0-9-]+@sdu\.edu\.kz)>', arg, re.I)
                recipient = match[1].lower() if match else None
                reply = b'250 local sink only\r\n' if recipient else b'550 synthetic recipient required\r\n'
            elif verb == 'DATA' and authenticated and recipient:
                self.wfile.write(b'354 message\r\n'); self.wfile.flush()
                body = bytearray()
                while True:
                    chunk = self.rfile.readline(8192)
                    if chunk == b'.\r\n': break
                    if not chunk or len(body) > 65536: return
                    body.extend(chunk[1:] if chunk.startswith(b'..') else chunk)
                message = BytesParser(policy=policy.default).parsebytes(body)
                if message['To'] != recipient or message['Subject'] != 'Student Marketplace: university email verification': return
                code = re.search(r'code is: ([0-9]{6})\b', message.get_content())
                if not code: return
                # Exact unique recipient, registration purpose, atomic new message only.
                destination = ROOT/'mail'/ (recipient + '.json')
                if destination.exists(): return
                temporary = ROOT/'mail'/ (uuid.uuid4().hex + '.tmp')
                temporary.write_text(json.dumps({'code':code[1], 'purpose':'registration', 'tls':secure, 'authenticated':authenticated}))
                temporary.rename(destination)
                reply = b'250 stored privately\r\n'
            elif verb == 'QUIT':
                self.wfile.write(b'221 bye\r\n'); return
            self.wfile.write(reply); self.wfile.flush()

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    with Server((os.environ.get('E2E_SMTP_BIND', '0.0.0.0'), int(os.environ.get('E2E_SMTP_PORT', '2525'))), Handler) as server: server.serve_forever()
