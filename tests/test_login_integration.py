from datetime import datetime, timezone
import logging
import unittest
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.models import EmailCode, RefreshSession, User
from backend.tokens import AUDIENCE, ISSUER
from postgresql_support import open_disposable_database


PASSWORD = "TEST_LOGIN_PASSWORD_MARKER_123"


class LoginPostgreSQLTest(unittest.TestCase):
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
        self.app = create_app(self.settings, self.database, sender=self.sender, clock=lambda: self.now)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def user(self, email="student@sdu.edu.kz", password=PASSWORD, **values):
        with self.database.session() as session:
            user = User(email=email, password_hash=PasswordHasher().hash(password), verified=True, **values)
            session.add(user)
            session.flush()
        return user

    def login(self, email="student@sdu.edu.kz", password=PASSWORD):
        return self.client.post("/auth/login", json={"email": email, "password": password})

    def test_login_claims_guard_and_access_only_state(self):
        user = self.user()
        response = self.login(" STUDENT@SDU.EDU.KZ ")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"access_token", "token_type", "expires_in"})
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(body["expires_in"], 900)
        self.assertNotIn("set-cookie", response.headers)
        claims = jwt.decode(body["access_token"], options={"verify_signature": False})
        self.assertEqual(set(claims), {"iss", "aud", "sub", "type", "iat", "exp", "jti"})
        self.assertEqual((claims["iss"], claims["aud"], claims["sub"], claims["type"]), (ISSUER, AUDIENCE, str(user.id), "access"))
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        protected = self.client.get("/auth/me", headers={"Authorization": "Bearer " + body["access_token"]})
        self.assertEqual(protected.status_code, 200)
        self.assertEqual(protected.json(), {"id": user.id, "email": "student@sdu.edu.kz", "verified": True})
        with self.database.session() as session:
            for model in (EmailCode, RefreshSession):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)
        self.sender.send_code.assert_not_called()

    def test_unknown_wrong_unverified_and_suspended_share_safe_rejection(self):
        user = self.user()
        responses = [self.login("unknown@sdu.edu.kz"), self.login(password="INCORRECT_TEST_PASSWORD")]
        with self.database.session() as session:
            session.get(User, user.id).verified = False
        responses.append(self.login())
        with self.database.session() as session:
            stored = session.get(User, user.id)
            stored.verified, stored.suspended = True, True
        responses.append(self.login())
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid credentials or account unavailable."})
            self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
            self.assertNotIn(PASSWORD, response.text)

    def test_current_database_suspension_unverification_and_deletion_reject_old_token(self):
        user = self.user()
        token = self.login().json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        for field in ("suspended", "verified"):
            with self.database.session() as session:
                stored = session.get(User, user.id)
                setattr(stored, field, field == "suspended")
            response = self.client.get("/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)
            with self.database.session() as session:
                stored = session.get(User, user.id)
                stored.suspended, stored.verified = False, True
        with self.database.session() as session:
            session.execute(delete(User).where(User.id == user.id))
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)

    def test_missing_malformed_bearer_and_invalid_token_are_safe(self):
        for authorization in (None, "Basic abc", "Bearer", "Bearer SENSITIVE_TOKEN_MARKER"):
            headers = {} if authorization is None else {"Authorization": authorization}
            response = self.client.get("/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Authentication required."})
            self.assertNotIn("SENSITIVE_", response.text)

    def test_password_case_whitespace_and_length_boundaries_are_preserved(self):
        for index, password in enumerate(("a" * 12, "B" * 128, "  TEST_SPACED_PASSWORD_123  ")):
            email = f"boundary{index}@sdu.edu.kz"
            self.user(email=email, password=password)
            self.assertEqual(self.login(email, password).status_code, 200)
            if password != password.strip():
                self.assertEqual(self.login(email, password.strip()).status_code, 401)
        self.assertEqual(self.login("boundary1@sdu.edu.kz", "b" * 128).status_code, 401)
        for password in ("a" * 11, "a" * 129, 123456789012, True, None):
            self.assertEqual(self.login("boundary0@sdu.edu.kz", password).status_code, 422)

    def test_unknown_missing_and_malformed_login_inputs_are_sanitized(self):
        for body in ({}, {"email": "student@sdu.edu.kz"}, {"password": PASSWORD},
            {"email": "student@sub.sdu.edu.kz", "password": PASSWORD},
            {"email": None, "password": PASSWORD},
            {"email": "student@sdu.edu.kz", "password": PASSWORD, "duration": 9999}):
            response = self.client.post("/auth/login", json=body)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid login request."})
            self.assertNotIn(PASSWORD, response.text)

    def test_database_errors_and_logs_do_not_expose_password_or_driver_values(self):
        messages = []
        class Capture(logging.Handler):
            def emit(self, record):
                messages.append(record.getMessage())
        handler = Capture()
        logger = logging.getLogger()
        logger.addHandler(handler)
        try:
            error = OperationalError("SENSITIVE_DB_URL_MARKER", {}, Exception("SENSITIVE_DB_SECRET_MARKER"))
            with patch("backend.routers.auth.authenticate_student", side_effect=error):
                response = self.login()
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json(), {"detail": "Authentication is temporarily unavailable."})
        finally:
            logger.removeHandler(handler)
        output = response.text + "\n".join(messages)
        self.assertNotIn("SENSITIVE_", output)
        self.assertNotIn(PASSWORD, output)
