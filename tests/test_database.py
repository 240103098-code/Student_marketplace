import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.exc import OperationalError

from backend.config import REPOSITORY_ROOT, load_settings
from backend.database import Base, Database, main


def isolated_settings():
    return load_settings(environ={
        "DATABASE_URL": "postgresql://test_user:TEST_PASSWORD_MARKER@localhost/test_database",
        "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40,
    }, env_file=None)


class DatabaseInfrastructureTest(unittest.TestCase):
    def test_import_does_not_load_settings_or_connect(self):
        result = subprocess.run([
            sys.executable, "-c",
            "from unittest.mock import patch;\nwith patch('backend.config.load_settings', side_effect=AssertionError), patch('sqlalchemy.create_engine', side_effect=AssertionError):\n import backend.database",
        ], cwd=REPOSITORY_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_engine_configuration_is_injected_lazy_and_bounded(self):
        with patch("backend.database.create_engine") as create, patch("backend.database.sessionmaker") as sessions:
            database = Database(isolated_settings())
            url = create.call_args.args[0]
            self.assertEqual(url.drivername, "postgresql+psycopg")
            self.assertEqual(create.call_args.kwargs["connect_args"]["connect_timeout"], 3)
            self.assertTrue(create.call_args.kwargs["hide_parameters"])
            create.return_value.connect.assert_not_called()
            sessions.assert_called_once_with(bind=database.engine, expire_on_commit=False)
        self.assertEqual(list(Base.metadata.tables), [])

    def test_successful_session_commits_and_closes(self):
        database = Database.__new__(Database)
        session = Mock()
        database.session_factory = Mock(return_value=session)
        with database.session() as obtained:
            self.assertIs(obtained, session)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.close.assert_called_once()

    def test_failed_work_rolls_back_and_closes(self):
        database = Database.__new__(Database)
        session = Mock()
        database.session_factory = Mock(return_value=session)
        with self.assertRaises(RuntimeError):
            with database.session():
                raise RuntimeError("synthetic failed work")
        session.commit.assert_not_called()
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    def test_failed_commit_rolls_back_and_closes(self):
        database = Database.__new__(Database)
        session = Mock()
        session.commit.side_effect = RuntimeError("synthetic failed commit")
        database.session_factory = Mock(return_value=session)
        with self.assertRaises(RuntimeError):
            with database.session():
                pass
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    def test_engine_disposal(self):
        database = Database.__new__(Database)
        database.engine = Mock()
        database.dispose()
        database.engine.dispose.assert_called_once()

    def test_cli_sanitizes_driver_failure_and_disposes(self):
        output = io.StringIO()
        with patch("backend.database.load_settings", return_value=isolated_settings()), patch("backend.database.Database") as factory, contextlib.redirect_stdout(output):
            factory.return_value.check_connection.side_effect = OperationalError(
                "TEST_PASSWORD_MARKER", {}, Exception("TEST_PASSWORD_MARKER")
            )
            self.assertEqual(main(["check"]), 1)
            factory.return_value.dispose.assert_called_once()
        self.assertIn("failed", output.getvalue())
        self.assertNotIn("TEST_PASSWORD_MARKER", output.getvalue())
