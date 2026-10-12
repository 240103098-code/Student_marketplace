"""Opt-in tests that mutate only an explicitly confirmed disposable PostgreSQL DB."""

import os
import subprocess
import sys
import time
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from backend.config import REPOSITORY_ROOT, load_settings
from backend.database import Database


class PostgreSQLIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_url = os.environ.get("TEST_DATABASE_URL")
        if not raw_url:
            raise unittest.SkipTest("Set dedicated TEST_DATABASE_URL and matching TEST_DATABASE_CONFIRM to run real PostgreSQL tests")
        url = make_url(raw_url)
        if (
            url.drivername not in {"postgresql", "postgresql+psycopg"}
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or not url.database
            or not url.database.startswith("student_marketplace_test_")
            or os.environ.get("TEST_DATABASE_CONFIRM") != url.database
        ):
            raise ValueError("Integration tests require an explicitly confirmed disposable loopback PostgreSQL test database")
        cls.environment = {
            "APP_ENV": "test", "DATABASE_URL": raw_url,
            "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40,
        }
        cls.settings = load_settings(environ=cls.environment, env_file=None)
        cls.database = Database(cls.settings)
        cls.addClassCleanup(cls.database.dispose)
        with cls.database.engine.connect() as connection:
            if connection.execute(text("SELECT current_database()")).scalar_one() != url.database:
                raise ValueError("Connected database does not match the disposable test database")
            tables = set(inspect(connection).get_table_names())
            if tables - {"alembic_version"}:
                raise ValueError("Disposable test database must contain no application tables")

    def migration_config(self):
        configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        configuration.attributes["settings"] = self.settings
        return configuration

    def test_real_postgresql_connection_and_migration_roundtrip(self):
        self.assertTrue(self.database.check_connection())
        configuration = self.migration_config()
        try:
            command.upgrade(configuration, "head")
            with self.database.engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), "0001_baseline")
            command.downgrade(configuration, "base")
            with self.database.engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one(), 0)
            command.upgrade(configuration, "head")
            with self.database.engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), "0001_baseline")
        finally:
            command.downgrade(configuration, "base")

    def test_real_postgresql_transaction_cleanup(self):
        with self.database.session() as session:
            session.execute(text("CREATE TEMP TABLE issue4_success (value integer) ON COMMIT DROP"))
            session.execute(text("INSERT INTO issue4_success VALUES (1)"))
            self.assertEqual(session.execute(text("SELECT value FROM issue4_success")).scalar_one(), 1)
        with self.database.session() as session:
            self.assertIsNone(session.execute(text("SELECT to_regclass('pg_temp.issue4_success')")).scalar_one())
        with self.assertRaises(RuntimeError):
            with self.database.session() as session:
                session.execute(text("CREATE TEMP TABLE issue4_failure (value integer)"))
                raise RuntimeError("synthetic rollback probe")
        with self.database.session() as session:
            self.assertIsNone(session.execute(text("SELECT to_regclass('pg_temp.issue4_failure')")).scalar_one())

    def test_real_postgresql_cli_success_and_unreachable_failure(self):
        environment = os.environ.copy() | self.environment
        # Disable any ignored development .env by injecting all required values;
        # no submitted values are ever printed by the command.
        result = subprocess.run([sys.executable, "-m", "backend.database", "check"], cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("succeeded", result.stdout)
        environment["DATABASE_URL"] = "postgresql://test_user:TEST_FAILURE_MARKER@127.0.0.1:1/student_marketplace_test_unreachable"
        start = time.monotonic()
        failure = subprocess.run([sys.executable, "-m", "backend.database", "check"], cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(failure.returncode, 0)
        self.assertLess(time.monotonic() - start, 15)
        self.assertNotIn("TEST_FAILURE_MARKER", failure.stdout + failure.stderr)
        self.assertNotIn("postgresql://", failure.stdout + failure.stderr)
