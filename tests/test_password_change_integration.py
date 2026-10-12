from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app import create_app
from backend.authentication import authenticate_student
from backend.config import REPOSITORY_ROOT
from backend.models import RefreshSession, User
from backend.sessions import COOKIE_NAME, revoke_user_sessions
from postgresql_support import open_disposable_database

OLD = 'TEST_CURRENT_PASSWORD_MARKER_123'
NEW = 'TEST_NEW_PASSWORD_MARKER_456'
ORIGIN = 'http://localhost:5173'


class PasswordChangePostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / 'alembic.ini'))
        cls.configuration.attributes['settings'] = cls.settings
        command.upgrade(cls.configuration, 'head')
        cls.addClassCleanup(command.downgrade, cls.configuration, '0001_baseline')

    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.app = create_app(self.settings, self.database, clock=lambda: self.now)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        with self.database.session() as session:
            self.user = User(email='student@sdu.edu.kz', password_hash=PasswordHasher().hash(OLD), verified=True, name='Student', phone='+77001234567', telegram_username='student_handle', external_contact_url='https://example.test/contact', avatar_path='avatar.png')
            session.add(self.user)
            session.flush()
        self.token = self.login().json()['access_token']

    def tearDown(self):
        self.context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def login(self, password=OLD, email='student@sdu.edu.kz'):
        return self.client.post('/auth/login', json={'email': email, 'password': password}, headers={'Origin': ORIGIN})

    def change(self, current=OLD, new=NEW, **extra):
        return self.client.post('/auth/change-password', json={'current_password': current, 'new_password': new, **extra}, headers={'Authorization': 'Bearer ' + self.token})

    def snapshot(self):
        with self.database.session() as session:
            user = session.get(User, self.user.id)
            records = list(session.scalars(select(RefreshSession).where(RefreshSession.user_id == self.user.id).order_by(RefreshSession.id)))
            return user.password_hash, [(r.id, r.token_digest, r.revoked_at) for r in records]

    def test_success_revokes_all_families_preserves_profile_and_other_account(self):
        first = self.token
        second = self.login().json()['access_token']
        raw = self.client.cookies.get(COOKIE_NAME)
        csrf = self.client.get('/auth/csrf').json()['csrf_token']
        with self.database.session() as session:
            other = User(email='other@sdu.edu.kz', password_hash=PasswordHasher().hash(OLD), verified=True)
            session.add(other)
            session.flush()
        other_token = self.login(email=other.email).json()['access_token']
        result = self.change()
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.content, b'')
        cookie = result.headers['set-cookie'].lower()
        self.assertTrue('max-age=0' in cookie and 'path=/auth' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie)
        self.assertNotIn('domain=', cookie)
        password_hash, sessions = self.snapshot()
        self.assertTrue(PasswordHasher().verify(password_hash, NEW))
        self.assertTrue(password_hash.startswith('$argon2id$'))
        self.assertTrue(all(row[2] is not None for row in sessions))
        for token in [first, second]:
            self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)
        self.assertEqual(self.client.post('/auth/refresh', headers={'Cookie': f'{COOKIE_NAME}={raw}', 'Origin': ORIGIN, 'X-CSRF-Token': csrf}).status_code, 401)
        self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + other_token}).status_code, 200)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(NEW).status_code, 200)
        with self.database.session() as session:
            current = session.get(User, self.user.id)
            self.assertEqual((current.email, current.verified, current.suspended, current.role, current.name, current.phone, current.telegram_username, current.external_contact_url, current.avatar_path), ('student@sdu.edu.kz', True, False, 'student', 'Student', '+77001234567', 'student_handle', 'https://example.test/contact', 'avatar.png'))
            self.assertTrue(PasswordHasher().verify(session.get(User, other.id).password_hash, OLD))

    def test_wrong_current_and_invalid_inputs_preserve_hash_and_sessions(self):
        before = self.snapshot()
        result = self.change(current='WRONG_PASSWORD_MARKER_123')
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json(), {'detail': 'Current password is incorrect.'})
        self.assertEqual(self.snapshot(), before)
        invalid = [dict(current_password=OLD, new_password='x'*11), dict(current_password=OLD, new_password='x'*129), dict(current_password='x'*11, new_password=NEW), dict(current_password='x'*129, new_password=NEW), dict(current_password=123456789012, new_password=NEW), dict(current_password=OLD, new_password=None), dict(current_password=OLD, new_password=NEW, user_id=999), dict(new_password=NEW)]
        for payload in invalid:
            with self.subTest(payload_fields=tuple(payload)):
                result = self.client.post('/auth/change-password', json=payload, headers={'Authorization': 'Bearer '+self.token})
                self.assertEqual(result.status_code, 422)
                self.assertEqual(result.json(), {'detail': 'Invalid password-change request.'})
                self.assertNotIn(OLD, result.text)
                self.assertEqual(self.snapshot(), before)

    def test_new_password_boundaries_and_spaces_are_not_trimmed(self):
        for new in [' 1234567890 ', 'x'*128]:
            self.assertEqual(self.change(new=new).status_code, 204)
            self.assertEqual(self.login(new.strip() if new.startswith(' ') else NEW).status_code, 422 if new.startswith(' ') else 401)
            result = self.login(new)
            self.assertEqual(result.status_code, 200)
            self.token = result.json()['access_token']
            self.assertEqual(self.change(current=new, new=OLD).status_code, 204)
            self.token = self.login().json()['access_token']

    def test_missing_expired_revoked_and_current_ineligibility_are_rejected(self):
        self.assertEqual(self.client.post('/auth/change-password', json={'current_password': OLD, 'new_password': NEW}).status_code, 401)
        for flag in ['suspended', 'verified']:
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'suspended')
            self.assertEqual(self.change().status_code, 401)
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'verified')
        with self.database.session() as session:
            revoke_user_sessions(session, self.user.id, self.now)
        self.assertEqual(self.change().status_code, 401)
        self.token = self.login().json()['access_token']
        from datetime import timedelta
        self.now += timedelta(minutes=15)
        self.assertEqual(self.change().status_code, 401)
        with self.database.session() as session:
            session.delete(session.get(User, self.user.id))
        self.assertEqual(self.change().status_code, 401)

    def test_revocation_failure_rolls_back_hash_and_never_leaks_inputs(self):
        before = self.snapshot()
        with patch('backend.passwords.revoke_user_sessions', side_effect=SQLAlchemyError('SENSITIVE_DRIVER_MARKER')):
            result = self.change()
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json(), {'detail': 'Authentication is temporarily unavailable.'})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login(NEW).status_code, 401)

    def test_login_verified_before_change_cannot_create_stale_password_session(self):
        authenticated, release = Event(), Event()
        def paused_auth(*args):
            user = authenticate_student(*args)
            authenticated.set()
            if not release.wait(5):
                raise RuntimeError('Test synchronization timed out')
            return user
        with patch('backend.routers.auth.authenticate_student', side_effect=paused_auth):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.login)
                self.assertTrue(authenticated.wait(5))
                try:
                    self.assertEqual(self.change().status_code, 204)
                finally:
                    release.set()
                self.assertEqual(pending.result(timeout=5).status_code, 401)
        self.assertTrue(all(row[2] is not None for row in self.snapshot()[1]))
        self.assertEqual(self.login(NEW).status_code, 200)

    def test_refresh_waiting_for_password_change_cannot_leave_active_prechange_family(self):
        raw = self.client.cookies.get(COOKIE_NAME)
        csrf = self.client.get('/auth/csrf').json()['csrf_token']
        locked, release = Event(), Event()
        def paused_revoke(*args):
            locked.set()
            if not release.wait(5):
                raise RuntimeError('Test synchronization timed out')
            return revoke_user_sessions(*args)
        with patch('backend.passwords.revoke_user_sessions', side_effect=paused_revoke):
            with ThreadPoolExecutor(max_workers=2) as executor:
                changed = executor.submit(self.change)
                self.assertTrue(locked.wait(5))
                rotated = executor.submit(self.client.post, '/auth/refresh', headers={'Cookie': f'{COOKIE_NAME}={raw}', 'Origin': ORIGIN, 'X-CSRF-Token': csrf})
                release.set()
                self.assertEqual(changed.result(timeout=5).status_code, 204)
                self.assertEqual(rotated.result(timeout=5).status_code, 401)
        self.assertTrue(all(row[2] is not None for row in self.snapshot()[1]))
