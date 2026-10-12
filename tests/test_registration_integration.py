from concurrent.futures import ThreadPoolExecutor
import logging
import unittest
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.models import EmailCode, RefreshSession, User
from postgresql_support import open_disposable_database


PASSWORD = "TEST_REGISTRATION_MARKER_1234"


class RegistrationPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.configuration.attributes["settings"] = cls.settings
        command.upgrade(cls.configuration, "head")
        cls.addClassCleanup(command.downgrade, cls.configuration, "0001_baseline")

    def setUp(self):
        self.sender = Mock()
        self.app = create_app(self.settings, self.database, sender=self.sender)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def count_users(self):
        with self.database.session() as session:
            return session.scalar(select(func.count()).select_from(User))

    def test_registration_persistence_normalization_and_argon2id(self):
        response = self.client.post("/auth/register", json={"email": " Student@SDU.EDU.KZ ", "password": PASSWORD})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body), {"id", "email", "verified"})
        self.assertEqual(body["email"], "student@sdu.edu.kz")
        self.assertFalse(body["verified"])
        with self.database.session() as session:
            user = session.get(User, body["id"])
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertTrue(PasswordHasher().verify(user.password_hash, PASSWORD))
            with self.assertRaises(VerifyMismatchError):
                PasswordHasher().verify(user.password_hash, "INCORRECT_SYNTHETIC_PASSWORD")
            self.assertFalse(user.verified)
            self.assertFalse(user.suspended)
            self.assertEqual(user.role, "student")
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(RefreshSession)), 0)
            self.assertNotIn(user.password_hash, response.text)
        self.assertNotIn(PASSWORD, response.text)
        self.sender.send_code.assert_called_once()

    def test_duplicate_unique_constraint_and_rollback(self):
        payload = {"email": "student@sdu.edu.kz", "password": PASSWORD}
        self.assertEqual(self.client.post("/auth/register", json=payload).status_code, 201)
        self.assertEqual(self.client.post("/auth/register", json=payload | {"email": " STUDENT@SDU.EDU.KZ "}).status_code, 409)
        self.assertEqual(self.count_users(), 1)
        self.assertEqual(self.sender.send_code.call_count, 1)
        self.assertEqual(self.client.post("/auth/register", json=payload | {"email": "another@sdu.edu.kz"}).status_code, 201)
        self.assertEqual(self.count_users(), 2)

    def test_concurrent_registration_keeps_exactly_one_account(self):
        def register(_):
            return self.client.post("/auth/register", json={"email": "race@sdu.edu.kz", "password": PASSWORD}).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(register, range(2))), [201, 409])
        self.assertEqual(self.count_users(), 1)

    def test_invalid_email_shapes_and_domains_never_persist(self):
        for email in (
            "student@sub.sdu.edu.kz", "student@sdu.edu.kz.evil.invalid", "student@sdu-edu.kz",
            "student@sdu.edu.Kz", "student@ｓdu.edu.kz", "student@sdu.edυ.kz",
            "missing-at", "@sdu.edu.kz", "two@@sdu.edu.kz", "two..dots@sdu.edu.kz",
            "name with space@sdu.edu.kz", "a" * 255 + "@sdu.edu.kz",
        ):
            with self.subTest(email=email):
                response = self.client.post("/auth/register", json={"email": email, "password": PASSWORD})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {"detail": "Invalid registration request."})
        self.assertEqual(self.count_users(), 0)

    def test_password_boundaries_are_untrimmed_and_not_coerced(self):
        for index, password in enumerate(("a" * 12, "b" * 128, " 1234567890 ")):
            response = self.client.post("/auth/register", json={"email": f"boundary{index}@sdu.edu.kz", "password": password})
            self.assertEqual(response.status_code, 201)
            with self.database.session() as session:
                user = session.get(User, response.json()["id"])
                self.assertTrue(PasswordHasher().verify(user.password_hash, password))
                if password != password.strip():
                    with self.assertRaises(VerifyMismatchError):
                        PasswordHasher().verify(user.password_hash, password.strip())
        for password in ("a" * 11, "b" * 129, 123456789012, True, None, ["a" * 12]):
            with self.subTest(password_type=type(password).__name__):
                self.assertEqual(self.client.post("/auth/register", json={"email": "invalid@sdu.edu.kz", "password": password}).status_code, 422)
        self.assertEqual(self.count_users(), 3)

    def test_missing_extra_wrong_type_and_malformed_json_are_sanitized(self):
        for body in ({}, {"email": "student@sdu.edu.kz"}, {"password": PASSWORD},
            {"email": 123, "password": PASSWORD}, {"email": None, "password": PASSWORD},
            {"email": "student@sdu.edu.kz", "password": PASSWORD, "role": "admin"},
            {"email": "student@sdu.edu.kz", "password": PASSWORD, "SENSITIVE_EXTRA_MARKER": "SENSITIVE_VALUE_MARKER"}):
            response = self.client.post("/auth/register", json=body)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(PASSWORD, response.text)
            self.assertNotIn("SENSITIVE_", response.text)
        response = self.client.post("/auth/register", content="{SENSITIVE_JSON_MARKER", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("SENSITIVE_JSON_MARKER", response.text)
        self.assertEqual(self.count_users(), 0)

    def test_unexpected_database_error_is_safe_and_logs_do_not_expose_input(self):
        messages = []
        class Capture(logging.Handler):
            def emit(self, record):
                messages.append(record.getMessage())
        handler = Capture()
        logger = logging.getLogger()
        logger.addHandler(handler)
        try:
            error = OperationalError("SENSITIVE_DB_URL_MARKER", {}, Exception("SENSITIVE_DB_SECRET_MARKER"))
            with patch("backend.routers.auth.register_student", side_effect=error):
                response = self.client.post("/auth/register", json={"email": "student@sdu.edu.kz", "password": PASSWORD})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json(), {"detail": "Registration is temporarily unavailable."})
            invalid = self.client.post("/auth/register", json={"email": "invalid", "password": PASSWORD})
            self.assertEqual(invalid.status_code, 422)
        finally:
            logger.removeHandler(handler)
        output = response.text + invalid.text + "\n".join(messages)
        self.assertNotIn(PASSWORD, output)
        self.assertNotIn("SENSITIVE_", output)
        self.assertEqual(self.count_users(), 0)
