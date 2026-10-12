"""Actual loopback SMTP protocol + dedicated PostgreSQL; no internet email."""

from datetime import timedelta
import re
import smtplib
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app import create_app
from backend.config import REPOSITORY_ROOT, load_settings
from backend.email_codes import code_digest, issue_email_code
from backend.mail import EmailDeliveryError, SmtpSender
from backend.models import EmailCode, User
from postgresql_support import open_disposable_database
from smtp_support import ExplicitTestSMTP, loopback_smtp


class VerificationDeliveryPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_settings, cls.database, cls.environment = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.configuration.attributes["settings"] = cls.base_settings
        command.upgrade(cls.configuration, "head")
        cls.addClassCleanup(command.downgrade, cls.configuration, "0001_baseline")

    def setUp(self):
        self.smtp_context = loopback_smtp()
        self.smtp = self.smtp_context.__enter__()
        self.settings = load_settings(environ=self.environment | {
            "SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(self.smtp.server_address[1]),
            "SMTP_USERNAME": "SYNTHETIC_SMTP_USER", "SMTP_PASSWORD": "SYNTHETIC_SMTP_PASSWORD",
            "SMTP_FROM_EMAIL": "verification@example.invalid",
        }, env_file=None)
        self.sender = SmtpSender(self.settings, smtp_factory=ExplicitTestSMTP)
        self.client_context = TestClient(create_app(self.settings, self.database, sender=self.sender))
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.smtp_context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def register(self):
        return self.client.post("/auth/register", json={"email": " Student@SDU.EDU.KZ ", "password": "TEST_SMTP_PASSWORD_MARKER_123"})

    def test_actual_mime_delivery_and_keyed_digest_persistence(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.smtp.messages), 1)
        sender, recipient, message = self.smtp.messages[0]
        self.assertEqual(sender, "verification@example.invalid")
        self.assertEqual(recipient, "student@sdu.edu.kz")
        self.assertEqual(message["To"], "student@sdu.edu.kz")
        self.assertIn("university email verification", message["Subject"])
        body = message.get_content()
        match = re.search(r"code is: (\d{6})", body)
        self.assertTrue(match is not None)
        raw_code = match.group(1)
        self.assertTrue("ten minutes" in body)
        self.assertTrue(raw_code not in response.text)
        with self.database.session() as session:
            record = session.scalar(select(EmailCode))
            self.assertEqual(record.purpose, "registration")
            self.assertEqual(record.wrong_attempts, 0)
            self.assertEqual(record.expires_at - record.created_at, timedelta(minutes=10))
            self.assertTrue(record.digest != raw_code)
            self.assertTrue(record.digest == code_digest(self.settings, record.user_id, "registration", raw_code))
            self.assertTrue(record.digest != code_digest(self.settings, record.user_id, "password_reset", raw_code))
            self.assertTrue(record.digest != code_digest(self.settings, record.user_id + 1, "registration", raw_code))
        duplicate = self.register()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(self.smtp.messages), 1)

    def test_replacement_invalidates_only_same_purpose(self):
        response = self.register()
        with self.database.session() as session:
            user = session.get(User, response.json()["id"])
            previous = session.scalar(select(EmailCode))
            previous_id = previous.id
            reset = issue_email_code(session, user, "password_reset", self.settings, self.sender)
            reset_id = reset.id
            replacement = issue_email_code(session, user, "registration", self.settings, self.sender)
            replacement_id = replacement.id
        with self.database.session() as session:
            self.assertIsNotNone(session.get(EmailCode, previous_id).invalidated_at)
            self.assertIsNone(session.get(EmailCode, reset_id).invalidated_at)
            self.assertIsNone(session.get(EmailCode, replacement_id).invalidated_at)

    def test_delivery_failure_rolls_back_replacement_and_preserves_previous_code(self):
        response = self.register()
        with self.database.session() as session:
            previous_id = session.scalar(select(EmailCode.id))
        failing_sender = SmtpSender(self.settings, smtp_factory=ExplicitTestSMTP)
        with patch.object(ExplicitTestSMTP, "send_message", side_effect=TimeoutError("SENSITIVE_TRANSPORT_MARKER")):
            with self.assertRaises(EmailDeliveryError):
                with self.database.session() as session:
                    user = session.get(User, response.json()["id"])
                    issue_email_code(session, user, "registration", self.settings, failing_sender)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)), 1)
            self.assertIsNone(session.get(EmailCode, previous_id).invalidated_at)

    def test_missing_smtp_returns_503_without_partial_account_or_code(self):
        with TestClient(create_app(self.base_settings, self.database)) as client:
            response = client.post("/auth/register", json={"email": "student@sdu.edu.kz", "password": "TEST_SMTP_PASSWORD_MARKER_123"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Verification email is temporarily unavailable."})
        with self.database.session() as session:
            for model in (User, EmailCode):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)

    def test_smtp_auth_recipient_tls_timeout_errors_are_safe_and_atomic(self):
        failures = [("login", smtplib.SMTPAuthenticationError(535, b"SENSITIVE_AUTH_MARKER")),
            ("send_message", smtplib.SMTPRecipientsRefused({"student@sdu.edu.kz": (550, b"refused")})),
            ("starttls", smtplib.SMTPException("SENSITIVE_TLS_MARKER")),
            ("send_message", TimeoutError("SENSITIVE_TIMEOUT_MARKER"))]
        for method, failure in failures:
            with self.subTest(method=method):
                with patch.object(ExplicitTestSMTP, method, side_effect=failure):
                    response = self.register()
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("SENSITIVE_", response.text)
                self.assertNotIn("TEST_SMTP_PASSWORD", response.text)
                with self.database.session() as session:
                    for model in (User, EmailCode):
                        self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)
