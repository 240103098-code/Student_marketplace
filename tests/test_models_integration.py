from datetime import datetime, timedelta, timezone
import unittest
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from backend.config import REPOSITORY_ROOT
from backend.models import Base, EmailCode, RefreshSession, User
from postgresql_support import open_disposable_database


class AccountSchemaPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.configuration.attributes["settings"] = cls.settings
        command.upgrade(cls.configuration, "0002_accounts")
        cls.addClassCleanup(command.downgrade, cls.configuration, "0001_baseline")

    def tearDown(self):
        # Only this freshly migrated, explicitly confirmed disposable schema.
        with self.database.session() as session:
            session.execute(delete(User))

    def user(self, email="student@sdu.edu.kz"):
        with self.database.session() as session:
            user = User(email=email, password_hash="$argon2id$SYNTHETIC_TEST_HASH")
            session.add(user)
            session.flush()
        return user

    def test_persisted_defaults_and_timezone_aware_timestamps(self):
        user = self.user(" Student@SDU.EDU.KZ ")
        self.assertEqual(user.email, "student@sdu.edu.kz")
        self.assertFalse(user.verified)
        self.assertFalse(user.suspended)
        self.assertEqual(user.role, "student")
        self.assertIsNotNone(user.created_at.tzinfo)
        self.assertIsNone(user.name)
        self.assertIsNone(user.avatar_path)

    def test_identity_uniqueness_domain_role_and_required_fields(self):
        self.user()
        for values in (
            {"email": "STUDENT@SDU.EDU.KZ"}, {"email": "student@sub.sdu.edu.kz"},
            {"email": "@sdu.edu.kz"}, {"email": "student@other.edu"},
            {"email": "another@sdu.edu.kz", "role": "owner"},
            {"email": "another@sdu.edu.kz", "password_hash": ""},
            {"email": "another@sdu.edu.kz", "password_hash": None},
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with self.database.session() as session:
                    session.add(User(**({"password_hash": "$argon2id$SYNTHETIC_TEST_HASH"} | values)))
        # Direct SQL bypassing the model must still reject non-normalized email.
        with self.assertRaises(IntegrityError):
            with self.database.session() as session:
                session.execute(text("INSERT INTO users(email,password_hash) VALUES ('OTHER@SDU.EDU.KZ','synthetic hash')"))

    def test_code_constraints_and_representable_expired_consumed_state(self):
        user = self.user()
        now = datetime.now(timezone.utc)
        for values in ({"purpose": "login"}, {"wrong_attempts": -1}, {"wrong_attempts": 6}, {"user_id": -1}, {"digest": ""}):
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with self.database.session() as session:
                    session.add(EmailCode(**({"user_id": user.id, "purpose": "registration", "digest": "a" * 64, "expires_at": now + timedelta(minutes=10)} | values)))
        with self.database.session() as session:
            code = EmailCode(user_id=user.id, purpose="password_reset", digest="b" * 64,
                created_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1),
                wrong_attempts=5, consumed_at=now, invalidated_at=now)
            session.add(code)
            session.flush()
            code_id = code.id
        with self.database.session() as session:
            stored = session.get(EmailCode, code_id)
            self.assertEqual(stored.purpose, "password_reset")
            self.assertEqual(stored.wrong_attempts, 5)
            for timestamp in (stored.created_at, stored.expires_at, stored.consumed_at, stored.invalidated_at):
                self.assertIsNotNone(timestamp.tzinfo)
            self.assertLess(stored.expires_at, now)

    def test_refresh_digest_uniqueness_fk_and_revocation_lineage(self):
        user = self.user()
        now = datetime.now(timezone.utc)
        family = uuid.uuid4()
        with self.database.session() as session:
            first = RefreshSession(user_id=user.id, token_digest="c" * 64, family_id=family, expires_at=now + timedelta(days=7))
            session.add(first)
            session.flush()
            second = RefreshSession(user_id=user.id, token_digest="d" * 64, family_id=family, predecessor_id=first.id, expires_at=now + timedelta(days=7))
            session.add(second)
            session.flush()
            first.successor_id = second.id
            first.revoked_at = now
            first_id, second_id = first.id, second.id
        for values in ({"token_digest": "c" * 64}, {"user_id": -1}, {"predecessor_id": uuid.uuid4()}, {"successor_id": uuid.uuid4()}, {"token_digest": ""}):
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with self.database.session() as session:
                    session.add(RefreshSession(**({"user_id": user.id, "token_digest": "e" * 64, "expires_at": now + timedelta(days=7)} | values)))
        with self.database.session() as session:
            first, second = session.get(RefreshSession, first_id), session.get(RefreshSession, second_id)
            self.assertEqual(first.successor_id, second.id)
            self.assertEqual(second.predecessor_id, first.id)
            self.assertEqual(first.family_id, second.family_id)
            self.assertIsNotNone(first.revoked_at.tzinfo)
            self.assertIsNotNone(second.created_at.tzinfo)

    def test_user_delete_cascades_and_leaves_no_dangling_links(self):
        user = self.user()
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        with self.database.session() as session:
            session.add(EmailCode(user_id=user.id, purpose="registration", digest="a" * 64, expires_at=expires))
            first = RefreshSession(user_id=user.id, token_digest="b" * 64, expires_at=expires)
            session.add(first)
            session.flush()
            second = RefreshSession(user_id=user.id, token_digest="c" * 64, family_id=first.family_id, predecessor_id=first.id, expires_at=expires)
            session.add(second)
            session.flush()
            first.successor_id = second.id
        with self.database.session() as session:
            session.execute(delete(User).where(User.id == user.id))
        with self.database.session() as session:
            for model in (User, EmailCode, RefreshSession):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)

    def test_schema_upgrade_downgrade_and_reupgrade(self):
        expected = {"alembic_version", "users", "email_codes", "refresh_sessions"}
        with self.database.engine.connect() as connection:
            inspector = inspect(connection)
            self.assertEqual(set(inspector.get_table_names()), expected)
            self.assertIn("ix_email_codes_user_purpose", {item["name"] for item in inspector.get_indexes("email_codes")})
            self.assertIn("ix_refresh_sessions_user_family", {item["name"] for item in inspector.get_indexes("refresh_sessions")})
            self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), "0002_accounts")
        command.downgrade(self.configuration, "0001_baseline")
        with self.database.engine.connect() as connection:
            self.assertEqual(set(inspect(connection).get_table_names()), {"alembic_version"})
        command.upgrade(self.configuration, "0002_accounts")
        with self.database.engine.connect() as connection:
            self.assertEqual(set(inspect(connection).get_table_names()), expected)
