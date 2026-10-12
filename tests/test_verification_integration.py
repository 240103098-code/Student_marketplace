from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.email_codes import issue_email_code
from backend.mail import EmailDeliveryError
from backend.models import EmailCode, RefreshSession, User
from postgresql_support import open_disposable_database


class VerificationPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.configuration.attributes["settings"] = cls.settings
        command.upgrade(cls.configuration, "head")
        cls.addClassCleanup(command.downgrade, cls.configuration, "0001_baseline")

    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.sender = Mock()
        self.client_context = TestClient(create_app(self.settings, self.database, sender=self.sender, clock=lambda: self.now))
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def register(self):
        with patch("backend.email_codes.secrets.randbelow", return_value=111111):
            result = self.client.post("/auth/register", json={"email": "student@sdu.edu.kz", "password": "TEST_VERIFICATION_PASSWORD_123"})
        self.assertEqual(result.status_code, 201)
        return result.json()["id"]

    def verify(self, code="111111", email="student@sdu.edu.kz"):
        return self.client.post("/auth/verify-email", json={"email": email, "code": code})

    def resend(self, email="student@sdu.edu.kz"):
        return self.client.post("/auth/resend-verification", json={"email": email})

    def test_success_consumption_and_replay(self):
        user_id = self.register()
        response = self.verify(email=" STUDENT@SDU.EDU.KZ ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"verified": True})
        self.assertEqual(self.verify().status_code, 400)
        with self.database.session() as session:
            self.assertTrue(session.get(User, user_id).verified)
            self.assertEqual(session.scalar(select(EmailCode)).consumed_at, self.now)
            self.assertEqual(session.scalar(select(func.count()).select_from(RefreshSession)), 0)

    def test_expiry_at_exact_ten_minute_boundary(self):
        self.register()
        self.now += timedelta(minutes=10)
        self.assertEqual(self.verify().status_code, 400)
        with self.database.session() as session:
            self.assertFalse(session.scalar(select(User)).verified)
            self.assertIsNone(session.scalar(select(EmailCode)).consumed_at)

    def test_code_just_before_expiry_is_usable(self):
        self.register()
        self.now += timedelta(minutes=10) - timedelta(microseconds=1)
        self.assertEqual(self.verify().status_code, 200)

    def test_wrong_attempts_persist_and_fifth_exhausts(self):
        self.register()
        for attempt in range(1, 6):
            self.assertEqual(self.verify("000000").status_code, 400)
            with self.database.session() as session:
                record = session.scalar(select(EmailCode))
                self.assertEqual(record.wrong_attempts, attempt)
                self.assertEqual(record.invalidated_at is not None, attempt == 5)
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.verify("000000").status_code, 400)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(EmailCode)).wrong_attempts, 5)
            self.assertFalse(session.scalar(select(User)).verified)
        self.now += timedelta(seconds=60)
        with patch("backend.email_codes.secrets.randbelow", return_value=222222):
            self.assertEqual(self.resend().status_code, 202)
        self.assertEqual(self.verify("222222").status_code, 200)

    def test_password_reset_purpose_unknown_verified_and_suspended_are_rejected(self):
        user_id = self.register()
        with self.database.session() as session, patch("backend.email_codes.secrets.randbelow", return_value=333333):
            user = session.get(User, user_id)
            issue_email_code(session, user, "password_reset", self.settings, self.sender, now=self.now)
        self.assertEqual(self.verify("333333").status_code, 400)
        self.assertEqual(self.verify(email="unknown@sdu.edu.kz").status_code, 400)
        with self.database.session() as session:
            session.get(User, user_id).suspended = True
        self.assertEqual(self.verify().status_code, 400)
        with self.database.session() as session:
            session.get(User, user_id).suspended = False
        self.assertEqual(self.verify().status_code, 200)
        self.assertEqual(self.verify().status_code, 400)

    def test_invalid_input_is_sanitized_and_does_not_increment_attempts(self):
        self.register()
        for code in (111111, None, "12345", "1234567", "١٢٣٤٥٦", "１２３４５６", " 11111", "abcdef"):
            response = self.client.post("/auth/verify-email", json={"email": "student@sdu.edu.kz", "code": code})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid verification request."})
        for endpoint, body in (("verify-email", {"email": "student@sub.sdu.edu.kz", "code": "111111"}),
            ("verify-email", {"email": "student@sdu.edu.kz", "code": "111111", "secret": "SENSITIVE_INPUT_MARKER"}),
            ("verify-email", {"email": "student@sdu.edu.kz"}),
            ("resend-verification", {"email": "student@sdu.edu.kz", "code": "111111"}),
            ("resend-verification", {"email": None})):
            response = self.client.post("/auth/" + endpoint, json=body)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("SENSITIVE_", response.text)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(EmailCode)).wrong_attempts, 0)

    def test_resend_cooldown_replacement_and_purpose_isolation(self):
        user_id = self.register()
        initial = self.resend()
        self.assertEqual(initial.status_code, 202)
        self.assertEqual(initial.headers["Retry-After"], "60")
        self.assertEqual(self.sender.send_code.call_count, 1)
        self.now += timedelta(seconds=60) - timedelta(microseconds=1)
        self.assertEqual(self.resend().json(), initial.json())
        self.assertEqual(self.sender.send_code.call_count, 1)
        with self.database.session() as session, patch("backend.email_codes.secrets.randbelow", return_value=333333):
            user = session.get(User, user_id)
            reset_id = issue_email_code(session, user, "password_reset", self.settings, self.sender, now=self.now).id
        self.now += timedelta(microseconds=1)
        # Force an initial random collision to prove an old raw value is rejected.
        with patch("backend.email_codes.secrets.randbelow", side_effect=[111111, 222222]):
            self.assertEqual(self.resend().json(), initial.json())
        with self.database.session() as session:
            latest = session.scalar(select(EmailCode).where(EmailCode.purpose == "registration").order_by(EmailCode.id.desc()))
            self.assertEqual(latest.wrong_attempts, 0)
            self.assertEqual(latest.expires_at - latest.created_at, timedelta(minutes=10))
            self.assertIsNone(session.get(EmailCode, reset_id).invalidated_at)
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.verify("222222").status_code, 200)

    def test_generic_resend_for_unknown_verified_suspended_and_cooldown(self):
        user_id = self.register()
        responses = [self.resend(), self.resend("unknown@sdu.edu.kz")]
        with self.database.session() as session:
            session.get(User, user_id).suspended = True
        responses.append(self.resend())
        with self.database.session() as session:
            user = session.get(User, user_id)
            user.suspended, user.verified = False, True
        responses.append(self.resend())
        for response in responses:
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json(), responses[0].json())
            self.assertEqual(response.headers["Retry-After"], "60")
        self.assertEqual(self.sender.send_code.call_count, 1)

    def test_failed_send_rolls_back_resend_and_preserves_old_code(self):
        self.register()
        self.now += timedelta(seconds=60)
        self.sender.send_code.side_effect = EmailDeliveryError("SENSITIVE_TRANSPORT_MARKER")
        response = self.resend()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SENSITIVE_", response.text)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)), 1)
            self.assertIsNone(session.scalar(select(EmailCode)).invalidated_at)
        self.assertEqual(self.verify().status_code, 200)

    def test_concurrent_correct_consumption_occurs_once(self):
        self.register()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.verify().status_code, range(2)))
        self.assertEqual(sorted(results), [200, 400])

    def test_concurrent_wrong_attempts_do_not_lose_updates_or_exceed_five(self):
        self.register()
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.verify("000000").status_code, range(8)))
        self.assertEqual(results, [400] * 8)
        with self.database.session() as session:
            record = session.scalar(select(EmailCode))
            self.assertEqual(record.wrong_attempts, 5)
            self.assertIsNotNone(record.invalidated_at)

    def test_concurrent_resend_sends_only_one_replacement(self):
        self.register()
        self.now += timedelta(seconds=60)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.resend().status_code, range(4)))
        self.assertEqual(results, [202] * 4)
        self.assertEqual(self.sender.send_code.call_count, 2)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)), 2)
