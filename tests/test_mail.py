import smtplib
import ssl
import unittest
from unittest.mock import Mock

from backend.config import load_settings
from backend.mail import EmailDeliveryError, SmtpSender


def smtp_settings(**overrides):
    return load_settings(environ={
        "DATABASE_URL": "postgresql://test_user@localhost/test_database",
        "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40,
        "SMTP_HOST": "smtp.example.invalid", "SMTP_PORT": "587",
        "SMTP_USERNAME": "SYNTHETIC_SMTP_USER", "SMTP_PASSWORD": "SYNTHETIC_SMTP_PASSWORD",
        "SMTP_FROM_EMAIL": "verification@example.invalid", **overrides,
    }, env_file=None)


class SmtpTransportTest(unittest.TestCase):
    def test_starttls_precedes_auth_and_uses_verified_context(self):
        connection = Mock()
        connection.send_message.return_value = {}
        factory = Mock(return_value=connection)
        SmtpSender(smtp_settings(), smtp_factory=factory).send_code("student@sdu.edu.kz", "000123", "registration")
        calls = [call[0] for call in connection.method_calls]
        self.assertEqual(calls, ["ehlo", "starttls", "ehlo", "login", "send_message", "quit", "close"])
        context = connection.starttls.call_args.kwargs["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(factory.call_args.kwargs["timeout"], 10)

    def test_tls_mode_uses_verified_smtp_ssl(self):
        connection = Mock()
        connection.send_message.return_value = {}
        ssl_factory = Mock(return_value=connection)
        sender = SmtpSender(smtp_settings(SMTP_SECURITY="tls", SMTP_PORT="465"), smtp_ssl_factory=ssl_factory)
        sender.send_code("student@sdu.edu.kz", "000123", "registration")
        context = ssl_factory.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        connection.starttls.assert_not_called()
        connection.close.assert_called_once()

    def test_transport_failures_are_sanitized_and_connections_close(self):
        cases = [("login", smtplib.SMTPAuthenticationError(535, b"SENSITIVE_AUTH_MARKER")),
            ("send_message", smtplib.SMTPRecipientsRefused({"student@sdu.edu.kz": (550, b"refused")})),
            ("starttls", ssl.SSLError("SENSITIVE_TLS_MARKER")),
            ("send_message", TimeoutError("SENSITIVE_TIMEOUT_MARKER"))]
        for method, failure in cases:
            with self.subTest(method=method):
                connection = Mock()
                getattr(connection, method).side_effect = failure
                with self.assertRaises(EmailDeliveryError) as error:
                    SmtpSender(smtp_settings(), smtp_factory=Mock(return_value=connection)).send_code("student@sdu.edu.kz", "000123", "registration")
                self.assertNotIn("SENSITIVE_", str(error.exception))
                connection.close.assert_called_once()
        connection = Mock()
        connection.send_message.return_value = {"student@sdu.edu.kz": (550, b"refused")}
        with self.assertRaises(EmailDeliveryError):
            SmtpSender(smtp_settings(), smtp_factory=Mock(return_value=connection)).send_code("student@sdu.edu.kz", "000123", "registration")
        connection.close.assert_called_once()

    def test_missing_configuration_never_connects(self):
        settings = load_settings(environ={"DATABASE_URL": "postgresql://test_user@localhost/test_database", "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40}, env_file=None)
        factory = Mock()
        with self.assertRaises(EmailDeliveryError):
            SmtpSender(settings, smtp_factory=factory).send_code("student@sdu.edu.kz", "000123", "registration")
        factory.assert_not_called()
