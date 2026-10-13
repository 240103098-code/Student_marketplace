from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.models import RefreshSession, User
from backend.profiles import update_own_profile
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database

PASSWORD = 'TEST_PROFILE_PASSWORD_MARKER_123'
PUBLIC_FIELDS = {'id', 'email', 'verified', 'name', 'phone', 'telegram_username', 'external_contact_url'}


class ProfilePostgreSQLTest(unittest.TestCase):
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
        self.context = TestClient(create_app(self.settings, self.database, clock=lambda: self.now))
        self.client = self.context.__enter__()
        with self.database.session() as session:
            self.user = User(email='student@sdu.edu.kz', password_hash=PasswordHasher().hash(PASSWORD), verified=True)
            self.other = User(email='other@sdu.edu.kz', password_hash=PasswordHasher().hash(PASSWORD), verified=True, name='Other')
            session.add_all([self.user, self.other])
            session.flush()
        self.token = self.login(self.user.email)
        self.other_token = self.login(self.other.email)
        self.headers = {'Authorization': 'Bearer '+self.token}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def login(self, email):
        response = self.client.post('/auth/login', json={'email': email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        return response.json()['access_token']

    def get(self):
        return self.client.get('/users/me', headers=self.headers)

    def edit(self, payload):
        return self.client.patch('/users/me', json=payload, headers=self.headers)

    def sensitive_snapshot(self):
        with self.database.session() as session:
            user = session.get(User, self.user.id)
            records = list(session.scalars(select(RefreshSession).where(RefreshSession.user_id == self.user.id).order_by(RefreshSession.id)))
            return (user.email, user.verified, user.suspended, user.role, user.password_hash, user.avatar_path), [(r.id, r.revoked_at, r.expires_at, r.token_digest) for r in records]

    def test_initial_null_profile_and_auth_me_contract_remain_minimal(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id': self.user.id, 'email': self.user.email, 'verified': True, 'name': None, 'phone': None, 'telegram_username': None, 'external_contact_url': None})
        self.assertEqual(self.client.get('/auth/me', headers=self.headers).json(), {'id': self.user.id, 'email': self.user.email, 'verified': True,'is_admin':False})
        self.assertNotIn(PASSWORD, response.text)

    def test_own_partial_edits_null_clearing_and_other_account_isolation(self):
        before = self.sensitive_snapshot()
        response = self.edit({'name': '  Student Name  ', 'phone': '+77001234567', 'telegram_username': 'student_1', 'external_contact_url': 'https://example.test/contact'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), PUBLIC_FIELDS)
        self.assertEqual(response.json()['name'], 'Student Name')
        result = self.edit({'name': 'Updated'})
        self.assertEqual(result.json()['phone'], '+77001234567')
        self.assertEqual(result.json()['telegram_username'], 'student_1')
        self.assertEqual(result.json()['external_contact_url'], 'https://example.test/contact')
        cleared = self.edit({'phone': None, 'telegram_username': None, 'external_contact_url': None})
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()['name'], 'Updated')
        self.assertTrue(all(cleared.json()[key] is None for key in ['phone', 'telegram_username', 'external_contact_url']))
        self.assertEqual(self.sensitive_snapshot(), before)
        other = self.client.get('/users/me', headers={'Authorization': 'Bearer '+self.other_token})
        self.assertEqual(other.json()['name'], 'Other')
        self.assertTrue(other.json()['phone'] is None)
        with self.database.session() as session:
            self.assertTrue(PasswordHasher().verify(session.get(User, self.other.id).password_hash, PASSWORD))

    def test_valid_name_and_contact_boundaries(self):
        for name in ['A', 'x'*100, '  A  ']:
            result = self.edit({'name': name})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['name'], name.strip())
        for phone in ['+1234567', '+'+'9'*15]:
            self.assertEqual(self.edit({'phone': phone}).status_code, 200)
        for telegram in ['abc_1', 'x'*32]:
            self.assertEqual(self.edit({'telegram_username': telegram}).status_code, 200)
        for url in ['https://example.test', 'https://example.test:443/path?contact=yes#here', 'https://127.0.0.1/contact', 'https://[::1]/contact', 'https://example.test/'+'x'*(2048-len('https://example.test/'))]:
            self.assertEqual(self.edit({'external_contact_url': url}).status_code, 200)

    def test_invalid_fields_and_formats_are_atomic_sanitized_rejections(self):
        self.edit({'name': 'Original', 'phone': '+77001234567'})
        before = self.get().json()
        invalid = [{}, {'name': None}, {'name': ''}, {'name': '   '}, {'name': 'x'*101}, {'name': 7}, {'phone': ''}, {'phone': '1234567'}, {'phone': '+123456'}, {'phone': '+'+'1'*16}, {'phone': '+١٢٣٤٥٦٧'}, {'phone': 123456789}, {'telegram_username': 'abcd'}, {'telegram_username': 'x'*33}, {'telegram_username': '@student'}, {'telegram_username': 'студент'}, {'telegram_username': ''}, {'external_contact_url': ''}, {'external_contact_url': 'http://example.test'}, {'external_contact_url': 'javascript:alert(1)'}, {'external_contact_url': 'https://user:pass@example.test'}, {'external_contact_url': 'https://example.test\n/path'}, {'external_contact_url': 'https://example.test/has space'}, {'external_contact_url': 'https:///missing'}, {'external_contact_url': 'https://-bad.test'}, {'external_contact_url': 'https://bad..test'}, {'external_contact_url': 'https://example.test:99999'}, {'external_contact_url': 'https://example.test/'+'x'*2048}, {'external_contact_url': 7}]
        for payload in invalid:
            with self.subTest(fields=tuple(payload)):
                result = self.edit(payload | ({'name': 'MUST_NOT_SAVE'} if 'name' not in payload and payload else {}))
                self.assertEqual(result.status_code, 422)
                self.assertEqual(result.json(), {'detail': 'Invalid profile request.'})
                self.assertEqual(self.get().json(), before)

    def test_protected_fields_and_other_account_identifiers_are_rejected(self):
        before = self.get().json()
        for key in ['id', 'user_id', 'email', 'role', 'verified', 'suspended', 'password', 'password_hash', 'avatar_path', 'refresh_sessions', 'token_digest', 'access_token']:
            result = self.edit({'name': 'MUST_NOT_SAVE', key: self.other.id})
            self.assertEqual(result.status_code, 422)
            self.assertEqual(self.get().json(), before)
        self.assertEqual(self.client.get(f'/users/{self.other.id}', headers=self.headers).status_code, 404)

    def test_missing_expired_revoked_and_ineligible_access(self):
        for method in [self.client.get, self.client.patch]:
            kwargs = {'json': {'name': 'No'}} if method == self.client.patch else {}
            self.assertEqual(method('/users/me', **kwargs).status_code, 401)
        for flag in ['verified', 'suspended']:
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'suspended')
            self.assertEqual(self.get().status_code, 401)
            self.assertEqual(self.edit({'name': 'No'}).status_code, 401)
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'verified')
        with self.database.session() as session:
            revoke_user_sessions(session, self.user.id, self.now)
        self.assertEqual(self.edit({'name': 'No'}).status_code, 401)
        self.headers = {'Authorization': 'Bearer '+self.login(self.user.email)}
        self.now += timedelta(minutes=15)
        self.assertEqual(self.edit({'name': 'No'}).status_code, 401)
        with self.database.session() as session:
            session.delete(session.get(User, self.user.id))
        self.assertEqual(self.get().status_code, 401)

    def test_database_failure_rolls_back_every_profile_field(self):
        before = self.get().json()
        original_flush = Session.flush
        def failing_flush(session, *args, **kwargs):
            if any(isinstance(record, User) and record.name == 'ROLLBACK_MARKER' for record in session.dirty):
                raise SQLAlchemyError('SENSITIVE_DRIVER_MARKER')
            return original_flush(session, *args, **kwargs)
        with patch.object(Session, 'flush', failing_flush):
            result = self.edit({'name': 'ROLLBACK_MARKER', 'phone': '+77001234567'})
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json(), {'detail': 'Profile is temporarily unavailable.'})
        self.assertEqual(self.get().json(), before)

    def test_stale_guard_cannot_edit_after_suspension_or_family_revocation(self):
        for mutation in ['suspend', 'revoke']:
            self.headers = {'Authorization': 'Bearer '+self.login(self.user.email)}
            ready, release = Event(), Event()
            def pause(*args, **kwargs):
                ready.set()
                if not release.wait(5): raise RuntimeError('Test synchronization timed out')
                return update_own_profile(*args, **kwargs)
            with patch('backend.routers.users.update_own_profile', side_effect=pause):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending = executor.submit(self.edit, {'name': 'MUST_NOT_SAVE'})
                    self.assertTrue(ready.wait(5))
                    try:
                        with self.database.session() as session:
                            if mutation == 'suspend': session.get(User, self.user.id).suspended = True
                            else: revoke_user_sessions(session, self.user.id, self.now)
                    finally: release.set()
                    self.assertEqual(pending.result(timeout=5).status_code, 401)
            with self.database.session() as session:
                user = session.get(User, self.user.id)
                self.assertIsNone(user.name)
                user.suspended = False

    def test_credentialed_patch_preflight_is_explicitly_allowed_only_for_configured_origin(self):
        headers = {'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PATCH', 'Access-Control-Request-Headers': 'authorization,content-type'}
        result = self.client.options('/users/me', headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers['Access-Control-Allow-Origin'], 'http://localhost:5173')
        self.assertEqual(result.headers['Access-Control-Allow-Credentials'], 'true')
        self.assertIn('PATCH', result.headers['Access-Control-Allow-Methods'])
        self.assertEqual(self.client.options('/users/me', headers=headers | {'Origin': 'https://evil.test'}).status_code, 400)
