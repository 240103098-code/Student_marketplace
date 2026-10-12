from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import re
from threading import Event
import unittest
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from backend.app import create_app
from backend.authentication import authenticate_student
from backend.config import REPOSITORY_ROOT, load_settings
from backend.email_codes import code_digest, issue_email_code
from backend.mail import EmailDeliveryError, SmtpSender
from backend.models import EmailCode, RefreshSession, User
from backend.sessions import COOKIE_NAME
from postgresql_support import open_disposable_database
from smtp_support import ExplicitTestSMTP, loopback_smtp

OLD = 'TEST_RECOVERY_OLD_PASSWORD_123'
NEW = 'TEST_RECOVERY_NEW_PASSWORD_456'
ORIGIN = 'http://localhost:5173'


class RecoveryPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, cls.environment = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / 'alembic.ini'))
        cls.configuration.attributes['settings'] = cls.settings
        command.upgrade(cls.configuration, 'head')
        cls.addClassCleanup(command.downgrade, cls.configuration, '0001_baseline')

    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.sender = Mock()
        self.app = create_app(self.settings, self.database, sender=self.sender, clock=lambda: self.now)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        with self.database.session() as session:
            self.user = User(email='student@sdu.edu.kz', password_hash=PasswordHasher().hash(OLD), verified=True, name='Student', phone='+77001234567')
            session.add(self.user)
            session.flush()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        with self.database.session() as session:
            session.execute(delete(User))

    def forgot(self, email='student@sdu.edu.kz'):
        return self.client.post('/auth/forgot-password', json={'email': email})

    def issue(self, raw=111111):
        with patch('backend.email_codes.secrets.randbelow', return_value=raw):
            result = self.forgot()
        self.assertEqual(result.status_code, 202)
        return result

    def reset(self, code='111111', email='student@sdu.edu.kz', password=NEW):
        return self.client.post('/auth/reset-password', json={'email': email, 'code': code, 'new_password': password})

    def login(self, password=OLD, email='student@sdu.edu.kz'):
        return self.client.post('/auth/login', json={'email': email, 'password': password}, headers={'Origin': ORIGIN})

    def codes(self):
        with self.database.session() as session:
            return list(session.scalars(select(EmailCode).where(EmailCode.user_id == self.user.id).order_by(EmailCode.id)))

    def test_actual_reset_mime_and_purpose_digest_never_return_plaintext(self):
        with loopback_smtp() as smtp:
            settings = load_settings(environ=self.environment | {'SMTP_HOST': '127.0.0.1', 'SMTP_PORT': str(smtp.server_address[1]), 'SMTP_USERNAME': 'SYNTHETIC_USER', 'SMTP_PASSWORD': 'SYNTHETIC_PASSWORD', 'SMTP_FROM_EMAIL': 'recovery@example.invalid'}, env_file=None)
            sender = SmtpSender(settings, smtp_factory=ExplicitTestSMTP)
            with TestClient(create_app(settings, self.database, sender=sender, clock=lambda: self.now)) as client:
                result = client.post('/auth/forgot-password', json={'email': ' Student@SDU.EDU.KZ '})
            self.assertEqual(result.status_code, 202)
            self.assertEqual(len(smtp.messages), 1)
            _, recipient, message = smtp.messages[0]
            self.assertEqual(recipient, self.user.email)
            self.assertIn('password', message['Subject'].lower())
            raw = re.search(r'code is: (\d{6})', message.get_content()).group(1)
            self.assertNotIn(raw, result.text)
            record = self.codes()[0]
            self.assertEqual(record.purpose, 'password_reset')
            self.assertEqual(record.digest, code_digest(settings, self.user.id, 'password_reset', raw))
            self.assertNotEqual(record.digest, raw)
            self.assertNotEqual(record.digest, code_digest(settings, self.user.id, 'registration', raw))
            self.assertEqual(record.expires_at-record.created_at, timedelta(minutes=10))

    def test_requests_are_generic_for_unknown_ineligible_cooldown_and_smtp_failure(self):
        expected = self.issue()
        for email in ['unknown@sdu.edu.kz', self.user.email]:
            result = self.forgot(email)
            self.assertEqual((result.status_code, result.json(), result.headers['Retry-After']), (202, expected.json(), '60'))
        self.assertEqual(self.sender.send_code.call_count, 1)
        for flag in ['verified', 'suspended']:
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'suspended')
            result = self.forgot()
            self.assertEqual(result.json(), expected.json())
            self.assertEqual(result.status_code, 202)
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'verified')
        self.now += timedelta(seconds=60)
        self.sender.send_code.side_effect = EmailDeliveryError('SENSITIVE_DELIVERY')
        with patch('backend.email_codes.secrets.randbelow', return_value=222222):
            result = self.forgot()
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json(), expected.json())
        self.assertEqual(len(self.codes()), 1)
        self.assertIsNone(self.codes()[0].invalidated_at)
        self.assertEqual(self.reset().status_code, 204)

    def test_replacement_cooldown_and_registration_purpose_are_independent(self):
        with self.database.session() as session, patch('backend.email_codes.secrets.randbelow', return_value=333333):
            issue_email_code(session, session.get(User, self.user.id), 'registration', self.settings, self.sender, now=self.now)
        self.issue()
        self.now += timedelta(seconds=59)
        self.forgot()
        self.assertEqual(len(self.codes()), 2)
        self.now += timedelta(seconds=1)
        self.issue(222222)
        records = self.codes()
        self.assertIsNone(records[0].invalidated_at)
        self.assertIsNotNone(records[1].invalidated_at)
        self.assertIsNone(records[2].invalidated_at)
        self.assertEqual(self.reset('111111').status_code, 400)
        self.assertEqual(self.reset('333333').status_code, 400)
        self.assertEqual(self.reset('222222').status_code, 204)
        self.assertIsNone(self.codes()[0].consumed_at)

    def test_wrong_attempts_persist_fifth_exhausts_and_concurrent_increments_are_bounded(self):
        self.issue()
        for attempt in range(1, 6):
            self.assertEqual(self.reset('000000').status_code, 400)
            self.assertEqual(self.codes()[0].wrong_attempts, attempt)
        self.assertIsNotNone(self.codes()[0].invalidated_at)
        self.assertEqual(self.reset().status_code, 400)
        self.now += timedelta(seconds=60)
        self.issue(222222)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.reset('000000'), range(9)))
        self.assertTrue(all(result.status_code == 400 for result in results))
        self.assertEqual(self.codes()[-1].wrong_attempts, 5)
        self.assertEqual(self.reset('222222').status_code, 400)

    def test_expiry_replay_and_concurrent_one_time_consumption(self):
        self.issue()
        self.now += timedelta(minutes=10)
        self.assertEqual(self.reset().status_code, 400)
        self.issue(222222)
        self.now += timedelta(minutes=10)-timedelta(microseconds=1)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.reset('222222'), range(2)))
        self.assertEqual(sorted(result.status_code for result in results), [204, 400])
        self.assertEqual(self.reset('222222').status_code, 400)
        self.assertIsNotNone(self.codes()[-1].consumed_at)

    def test_concurrent_request_sends_only_one_reset_message(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.forgot(), range(2)))
        self.assertTrue(all(result.status_code == 202 for result in results))
        self.assertEqual(self.sender.send_code.call_count, 1)
        self.assertEqual(len(self.codes()), 1)

    def test_reset_revokes_all_credentials_and_preserves_other_accounts_and_profile(self):
        first = self.login().json()['access_token']
        second = self.login().json()['access_token']
        raw = self.client.cookies.get(COOKIE_NAME)
        csrf = self.client.get('/auth/csrf').json()['csrf_token']
        with self.database.session() as session:
            other = User(email='other@sdu.edu.kz', password_hash=PasswordHasher().hash(OLD), verified=True)
            session.add(other)
            session.flush()
        other_token = self.login(email=other.email).json()['access_token']
        self.issue()
        result = self.reset()
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.content, b'')
        self.assertIn('Max-Age=0', result.headers['set-cookie'])
        self.assertIn('Path=/auth', result.headers['set-cookie'])
        for token in [first, second]:
            self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer '+token}).status_code, 401)
        self.assertEqual(self.client.post('/auth/refresh', headers={'Cookie': f'{COOKIE_NAME}={raw}', 'Origin': ORIGIN, 'X-CSRF-Token': csrf}).status_code, 401)
        self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer '+other_token}).status_code, 200)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(NEW).status_code, 200)
        with self.database.session() as session:
            user = session.get(User, self.user.id)
            self.assertTrue(PasswordHasher().verify(user.password_hash, NEW))
            self.assertEqual((user.email, user.verified, user.name, user.phone), (self.user.email, True, 'Student', '+77001234567'))
            self.assertTrue(PasswordHasher().verify(session.get(User, other.id).password_hash, OLD))

    def test_ineligible_unknown_and_cross_purpose_codes_cannot_activate_accounts(self):
        with self.database.session() as session, patch('backend.email_codes.secrets.randbelow', return_value=333333):
            issue_email_code(session, session.get(User, self.user.id), 'registration', self.settings, self.sender, now=self.now)
        self.assertEqual(self.reset('333333').status_code, 400)
        self.assertEqual(self.reset(email='unknown@sdu.edu.kz').status_code, 400)
        self.issue()
        for flag in ['verified', 'suspended']:
            with self.database.session() as session:
                setattr(session.get(User, self.user.id), flag, flag == 'suspended')
            self.assertEqual(self.reset().status_code, 400)
            with self.database.session() as session:
                user = session.get(User, self.user.id)
                self.assertEqual(getattr(user, flag), flag == 'suspended')
                self.assertTrue(PasswordHasher().verify(user.password_hash, OLD))
                setattr(user, flag, flag == 'verified')

    def test_validation_and_transaction_failure_never_consume_or_change_credentials(self):
        self.issue()
        valid = {'email': self.user.email, 'code': '111111', 'new_password': NEW}
        invalid = [valid | {'new_password': 'x'*11}, valid | {'new_password': 'x'*129}, valid | {'new_password': 123456789012}, valid | {'code': '١٢٣٤٥٦'}, valid | {'email': 'student@sub.sdu.edu.kz'}, valid | {'user_id': 999}, {'email': self.user.email}, valid | {'code': 111111}]
        for payload in invalid:
            result = self.client.post('/auth/reset-password', json=payload)
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json(), {'detail': 'Invalid password-reset request.'})
            self.assertNotIn(NEW, result.text)
        self.assertEqual(self.codes()[0].wrong_attempts, 0)
        with patch('backend.recovery.revoke_user_sessions', side_effect=SQLAlchemyError('SENSITIVE_DRIVER')):
            result = self.reset()
        self.assertEqual(result.status_code, 500)
        self.assertIsNone(self.codes()[0].consumed_at)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login(NEW).status_code, 401)
        self.assertEqual(self.reset(password=' 1234567890 ').status_code, 204)
        self.assertEqual(self.login(' 1234567890 ').status_code, 200)

    def test_preverified_old_login_cannot_create_active_session_after_reset(self):
        self.issue()
        ready, release = Event(), Event()
        def paused_auth(*args):
            user = authenticate_student(*args)
            ready.set()
            if not release.wait(5): raise RuntimeError('Test synchronization timed out')
            return user
        with patch('backend.routers.auth.authenticate_student', side_effect=paused_auth):
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.login)
                self.assertTrue(ready.wait(5))
                try: self.assertEqual(self.reset().status_code, 204)
                finally: release.set()
                self.assertEqual(pending.result(timeout=5).status_code, 401)
        with self.database.session() as session:
            self.assertTrue(all(record.revoked_at is not None for record in session.scalars(select(RefreshSession).where(RefreshSession.user_id == self.user.id))))
    def test_refresh_waiting_on_reset_cannot_keep_old_family_active(self):
        self.login()
        raw = self.client.cookies.get(COOKIE_NAME)
        csrf = self.client.get('/auth/csrf').json()['csrf_token']
        self.issue()
        ready, release = Event(), Event()
        from backend.sessions import revoke_user_sessions
        def paused_revoke(*args):
            ready.set()
            if not release.wait(5): raise RuntimeError('Test synchronization timed out')
            return revoke_user_sessions(*args)
        with patch('backend.recovery.revoke_user_sessions', side_effect=paused_revoke):
            with ThreadPoolExecutor(max_workers=2) as executor:
                reset = executor.submit(self.reset)
                self.assertTrue(ready.wait(5))
                refresh = executor.submit(self.client.post, '/auth/refresh', headers={'Cookie': f'{COOKIE_NAME}={raw}', 'Origin': ORIGIN, 'X-CSRF-Token': csrf})
                release.set()
                self.assertEqual(reset.result(timeout=5).status_code, 204)
                self.assertEqual(refresh.result(timeout=5).status_code, 401)
        with self.database.session() as session:
            self.assertTrue(all(record.revoked_at is not None for record in session.scalars(select(RefreshSession).where(RefreshSession.user_id == self.user.id))))

    def test_recovery_request_validation_is_safe_and_missing_smtp_still_returns_generic_acceptance(self):
        for payload in [{'email': 'student@sub.sdu.edu.kz'}, {'email': 7}, {'email': self.user.email, 'password': OLD}, {}]:
            result = self.client.post('/auth/forgot-password', json=payload)
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json(), {'detail': 'Invalid recovery request.'})
            self.assertNotIn(OLD, result.text)
        self.assertEqual(self.codes(), [])
        with TestClient(create_app(self.settings, self.database, clock=lambda: self.now)) as client:
            result = client.post('/auth/forgot-password', json={'email': self.user.email})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.headers['Retry-After'], '60')
        self.assertEqual(self.codes(), [])
