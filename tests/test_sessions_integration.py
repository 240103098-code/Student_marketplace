from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import unittest

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import delete, func, select

from backend.app import create_app
from backend.config import REPOSITORY_ROOT, load_settings
from backend.models import RefreshSession, User
from backend.sessions import COOKIE_NAME, refresh_digest, revoke_user_sessions
from backend.tokens import issue_access_token
from postgresql_support import open_disposable_database


ORIGIN = "http://localhost:5173"
PASSWORD = "TEST_REFRESH_PASSWORD_MARKER_123"


class RefreshSessionPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, cls.environment = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.configuration.attributes["settings"] = cls.settings
        command.upgrade(cls.configuration, "head")
        cls.addClassCleanup(command.downgrade, cls.configuration, "0001_baseline")

    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.app = create_app(self.settings, self.database, clock=lambda: self.now)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        with self.database.session() as session:
            self.user = User(email="student@sdu.edu.kz", password_hash=PasswordHasher().hash(PASSWORD), verified=True)
            session.add(self.user)
            session.flush()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def login(self, client=None, origin=ORIGIN):
        client = self.client if client is None else client
        response = client.post("/auth/login", json={"email": self.user.email, "password": PASSWORD}, headers={"Origin": origin})
        self.assertEqual(response.status_code, 200)
        raw = client.cookies.get(COOKIE_NAME)
        bootstrap = client.get("/auth/csrf", headers={"Origin": origin})
        self.assertEqual(bootstrap.status_code, 200)
        return response, raw, bootstrap.json()["csrf_token"]

    def headers(self, raw, csrf, origin=ORIGIN):
        return {"Cookie": f"{COOKIE_NAME}={raw}", "X-CSRF-Token": csrf, "Origin": origin}

    def protected(self, token):
        return self.client.get("/auth/me", headers={"Authorization": "Bearer " + token})

    def sessions(self):
        with self.database.session() as session:
            return list(session.scalars(select(RefreshSession).order_by(RefreshSession.created_at, RefreshSession.id)))

    def test_login_cookie_digest_storage_and_readonly_csrf_bootstrap(self):
        response, raw, csrf = self.login()
        cookie = response.headers["set-cookie"].lower()
        self.assertTrue("httponly" in cookie and "samesite=lax" in cookie and "path=/auth" in cookie)
        self.assertTrue("domain=" not in cookie and "secure" not in cookie)
        self.assertTrue("max-age=604800" in cookie)
        self.assertTrue(raw not in response.text)
        records = self.sessions()
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].token_digest == refresh_digest(raw))
        self.assertTrue(records[0].token_digest != raw)
        self.assertEqual(records[0].expires_at - records[0].created_at, timedelta(days=7))
        snapshot = [(r.id, r.revoked_at, r.predecessor_id, r.successor_id) for r in records]
        for _ in range(2):
            result = self.client.get("/auth/csrf", headers=self.headers(raw, csrf))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertEqual(snapshot, [(r.id, r.revoked_at, r.predecessor_id, r.successor_id) for r in self.sessions()])

    def test_rotation_preserves_fixed_expiry_and_access_family(self):
        response, raw, csrf = self.login()
        original_expiry = self.sessions()[0].expires_at
        self.now += timedelta(minutes=5)
        rotated = self.client.post("/auth/refresh", headers=self.headers(raw, csrf))
        self.assertEqual(rotated.status_code, 200)
        successor_raw = self.client.cookies.get(COOKIE_NAME)
        self.assertTrue(successor_raw != raw and successor_raw not in rotated.text)
        records = self.sessions()
        self.assertEqual(len(records), 2)
        predecessor = next(record for record in records if record.token_digest == refresh_digest(raw))
        successor = next(record for record in records if record.token_digest == refresh_digest(successor_raw))
        self.assertEqual(predecessor.successor_id, successor.id)
        self.assertEqual(successor.predecessor_id, predecessor.id)
        self.assertIsNotNone(predecessor.revoked_at)
        self.assertIsNone(successor.revoked_at)
        self.assertEqual(successor.expires_at, original_expiry)
        self.assertEqual(successor.family_id, predecessor.family_id)
        self.assertEqual(self.protected(rotated.json()["access_token"]).status_code, 200)
        # Both access tokens remain inside their normal fifteen-minute window.
        self.assertEqual(self.protected(response.json()["access_token"]).status_code, 200)

    def test_replayed_predecessor_revokes_successor_and_access_immediately(self):
        response, raw, csrf = self.login()
        rotated = self.client.post("/auth/refresh", headers=self.headers(raw, csrf))
        successor_raw = self.client.cookies.get(COOKIE_NAME)
        replay = self.client.post("/auth/refresh", headers=self.headers(raw, csrf))
        self.assertEqual(replay.status_code, 401)
        self.assertTrue(all(record.revoked_at is not None for record in self.sessions()))
        self.assertEqual(self.protected(response.json()["access_token"]).status_code, 401)
        self.assertEqual(self.protected(rotated.json()["access_token"]).status_code, 401)
        self.assertEqual(self.client.post("/auth/refresh", headers=self.headers(successor_raw, csrf)).status_code, 401)

    def test_concurrent_rotation_has_one_success_then_persisted_family_revocation(self):
        _, raw, csrf = self.login()
        headers = self.headers(raw, csrf)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: self.client.post("/auth/refresh", headers=headers), range(2)))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 401])
        records = self.sessions()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record.revoked_at is not None for record in records))
        winner = next(response for response in responses if response.status_code == 200)
        self.assertEqual(self.protected(winner.json()["access_token"]).status_code, 401)

    def test_logout_is_scoped_idempotent_and_clears_matching_cookie(self):
        first, raw1, csrf1 = self.login()
        second, raw2, csrf2 = self.login()
        with self.database.session() as session:
            other = User(email="other@sdu.edu.kz", password_hash=PasswordHasher().hash(PASSWORD), verified=True)
            session.add(other)
        other_login = self.client.post("/auth/login", json={"email": "other@sdu.edu.kz", "password": PASSWORD}, headers={"Origin": ORIGIN})
        self.assertEqual(other_login.status_code, 200)
        result = self.client.post("/auth/logout", headers=self.headers(raw1, csrf1))
        self.assertEqual(result.status_code, 204)
        deleted = result.headers["set-cookie"].lower()
        self.assertTrue("max-age=0" in deleted and "path=/auth" in deleted and "domain=" not in deleted)
        self.assertEqual(self.protected(first.json()["access_token"]).status_code, 401)
        self.assertEqual(self.protected(second.json()["access_token"]).status_code, 200)
        self.assertEqual(self.protected(other_login.json()["access_token"]).status_code, 200)
        for raw in (raw1, "x" * 64, "malformed"):
            self.assertEqual(self.client.post("/auth/logout", headers=self.headers(raw, csrf1)).status_code, 204)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf1}).status_code, 204)
        self.assertEqual(self.protected(second.json()["access_token"]).status_code, 200)
        self.assertEqual(len(self.sessions()), 3)

    def test_csrf_origin_and_cross_family_fail_before_mutation(self):
        _, raw1, csrf1 = self.login()
        _, raw2, csrf2 = self.login()
        snapshot = [(r.id, r.revoked_at) for r in self.sessions()]
        bad_headers = [
            {"Cookie": f"{COOKIE_NAME}={raw1}", "X-CSRF-Token": csrf1},
            self.headers(raw1, csrf1, "https://evil.invalid"),
            {"Cookie": f"{COOKIE_NAME}={raw1}", "Origin": ORIGIN},
            self.headers(raw1, "a" * 64), self.headers(raw2, csrf1),
        ]
        for endpoint in ("refresh", "logout"):
            for headers in bad_headers:
                self.assertEqual(self.client.post("/auth/" + endpoint, headers=headers).status_code, 403)
        self.assertEqual(snapshot, [(r.id, r.revoked_at) for r in self.sessions()])
        self.assertEqual(self.client.get("/auth/csrf", headers=self.headers(raw2, csrf2, "https://evil.invalid")).status_code, 403)

    def test_expiry_malformed_missing_and_eligibility_prevent_new_sessions(self):
        response, raw, csrf = self.login()
        for value in ("bad", "x" * 64):
            self.assertEqual(self.client.post("/auth/refresh", headers=self.headers(value, csrf)).status_code, 401)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/auth/refresh", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}).status_code, 401)
        self.now += timedelta(days=7)
        self.assertEqual(self.client.post("/auth/refresh", headers=self.headers(raw, csrf)).status_code, 401)
        self.assertEqual(len(self.sessions()), 1)
        self.assertEqual(self.protected(response.json()["access_token"]).status_code, 401)
        # Independently prove family expiry denies even a freshly signed JWT.
        expired_family = self.sessions()[0].family_id
        fresh_access = issue_access_token(self.settings, self.user.id, expired_family, clock=lambda: self.now)
        self.assertEqual(self.protected(fresh_access).status_code, 401)
        self.now -= timedelta(days=7)
        with self.database.session() as session:
            session.get(User, self.user.id).suspended = True
        self.assertEqual(self.client.post("/auth/refresh", headers=self.headers(raw, csrf)).status_code, 401)
        self.assertTrue(all(record.revoked_at is not None for record in self.sessions()))

    def test_unbound_access_token_and_userwide_revocation_are_rejected(self):
        response, _, _ = self.login()
        claims = jwt.decode(response.json()["access_token"], options={"verify_signature": False})
        del claims["sid"]
        unbound = jwt.encode(claims, self.settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
        self.assertEqual(self.protected(unbound).status_code, 401)
        with self.database.session() as session:
            revoke_user_sessions(session, self.user.id, self.now)
        self.assertEqual(self.protected(response.json()["access_token"]).status_code, 401)

    def test_login_origin_and_credentialed_cors_contract(self):
        bad = self.client.post("/auth/login", json={"email": self.user.email, "password": PASSWORD}, headers={"Origin": "https://evil.invalid"})
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(len(self.sessions()), 0)
        preflight = self.client.options("/auth/refresh", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "X-CSRF-Token,Content-Type"})
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers["Access-Control-Allow-Origin"], ORIGIN)
        self.assertEqual(preflight.headers["Access-Control-Allow-Credentials"], "true")
        denied = self.client.options("/auth/refresh", headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "POST"})
        self.assertEqual(denied.status_code, 400)
        self.assertNotIn("Access-Control-Allow-Origin", denied.headers)

    def test_production_cookie_secure_flags_and_deletion(self):
        origin = "https://campus.example.invalid"
        settings = load_settings(environ=self.environment | {"APP_ENV": "production", "FRONTEND_ORIGINS": '["https://campus.example.invalid"]'}, env_file=None)
        with TestClient(create_app(settings, self.database, clock=lambda: self.now), base_url="https://testserver") as client:
            response, raw, csrf = self.login(client, origin)
            cookie = response.headers["set-cookie"].lower()
            self.assertTrue("secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/auth" in cookie)
            self.assertTrue("domain=" not in cookie)
            result = client.post("/auth/logout", headers=self.headers(raw, csrf, origin))
            self.assertEqual(result.status_code, 204)
            self.assertTrue("secure" in result.headers["set-cookie"].lower())
