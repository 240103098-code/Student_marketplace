"""Memory-only loopback SMTP protocol fixture; no external mail is possible."""

from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
import smtplib
import socketserver
import ssl
import threading


class ProtocolHandler(socketserver.StreamRequestHandler):
    def handle(self):
        sender, recipient = None, None
        self.wfile.write(b"220 loopback.test SMTP ready\r\n")
        while line := self.rfile.readline():
            command = line.decode("ascii").strip()
            verb = command.split(" ", 1)[0].upper()
            if verb in {"EHLO", "HELO"}:
                self.wfile.write(b"250-loopback.test\r\n250 AUTH PLAIN\r\n")
            elif verb == "AUTH":
                self.wfile.write(b"235 authenticated test transport\r\n")
            elif verb == "MAIL":
                sender = command.split(":", 1)[1].strip().strip("<>")
                self.wfile.write(b"250 sender accepted\r\n")
            elif verb == "RCPT":
                recipient = command.split(":", 1)[1].strip().strip("<>")
                self.wfile.write(b"250 recipient accepted\r\n")
            elif verb == "DATA":
                self.wfile.write(b"354 send message\r\n")
                data = []
                while (body := self.rfile.readline()) not in {b".\r\n", b""}:
                    data.append(body[1:] if body.startswith(b"..") else body)
                self.server.messages.append((sender, recipient, BytesParser(policy=policy.default).parsebytes(b"".join(data))))
                self.wfile.write(b"250 stored only in fixture memory\r\n")
            elif verb == "QUIT":
                self.wfile.write(b"221 closing\r\n")
                break
            else:
                self.wfile.write(b"250 accepted\r\n")


class LoopbackServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ExplicitTestSMTP(smtplib.SMTP):
    """Test-only plaintext transport; production TLS behavior is tested separately."""
    def starttls(self, *, context):
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise AssertionError("Production context must still verify certificates")
        # This fixture deliberately exercises SMTP/MIME, not encrypted transport.
        return 220, b"test-only transport substitution"


@contextmanager
def loopback_smtp():
    server = LoopbackServer(("127.0.0.1", 0), ProtocolHandler)
    server.messages = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
