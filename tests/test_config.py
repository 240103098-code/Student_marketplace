import contextlib
import io
import os
from pathlib import Path
import tempfile
import traceback
import subprocess
import sys
import unittest
from unittest.mock import patch

from backend.config import REPOSITORY_ROOT, load_settings


def valid_environment(**overrides):
    # Synthetic test-only markers, never credentials for a running service.
    return {
        "DATABASE_URL": "postgresql://test_user:TEST_DB_MARKER@localhost/test_database",
        "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40,
        **overrides,
    }


class ConfigurationTest(unittest.TestCase):
    def load(self, **overrides):
        return load_settings(environ=valid_environment(**overrides), env_file=None)

    def test_defaults_and_rooted_uploads(self):
        settings = self.load()
        self.assertEqual(settings.university_email_domain, "sdu.edu.kz")
        self.assertEqual(settings.frontend_origins, ["http://localhost:5173"])
        self.assertEqual((settings.jwt_access_minutes, settings.refresh_session_days), (15, 7))
        self.assertEqual(settings.upload_dir, REPOSITORY_ROOT / "backend" / "uploads")
        self.assertTrue(settings.refresh_cookie_httponly)
        self.assertEqual(settings.refresh_cookie_samesite, "lax")

    def test_environment_over_file_over_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("JWT_ACCESS_MINUTES=25\nREFRESH_SESSION_DAYS=9\n", encoding="utf-8")
            settings = load_settings(environ=valid_environment(JWT_ACCESS_MINUTES="30"), env_file=env_file)
            self.assertEqual(settings.jwt_access_minutes, 30)
            self.assertEqual(settings.refresh_session_days, 9)
            self.assertEqual(settings.app_env, "development")

    def test_injected_environment_ignores_ambient_and_can_disable_file(self):
        with patch.dict(os.environ, {"JWT_ACCESS_MINUTES": "99"}):
            self.assertEqual(self.load().jwt_access_minutes, 15)
        with patch("backend.config.dotenv_values", side_effect=AssertionError("must not read file")):
            self.load()

    def test_import_does_not_read_configuration(self):
        result = subprocess.run(
            [sys.executable, "-c", "import os; from unittest.mock import patch; os.environ.pop('JWT_SECRET_KEY', None); os.environ.pop('DATABASE_URL', None);\nwith patch('dotenv.dotenv_values', side_effect=AssertionError):\n import backend.config"],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_required_secret_and_placeholder_failures(self):
        for value in (None, "", "short", "REPLACE_WITH_A_PRIVATE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS"):
            environment = valid_environment()
            if value is None:
                del environment["JWT_SECRET_KEY"]
            else:
                environment["JWT_SECRET_KEY"] = value
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                load_settings(environ=environment, env_file=None)
            self.assertIn("JWT_SECRET_KEY", str(error.exception))

    def test_invalid_types_domains_and_urls(self):
        invalid = {
            "APP_ENV": ["staging"],
            "DATABASE_URL": ["sqlite:///local.db", "postgresql://localhost", "postgresql://localhost:bad/db"],
            "UNIVERSITY_EMAIL_DOMAIN": ["other.edu", "sub.sdu.edu.kz"],
            "JWT_ACCESS_MINUTES": ["0", "-1", "words"],
            "REFRESH_SESSION_DAYS": ["0"],
            "FRONTEND_ORIGINS": ["*", '["*"]', '[]', '["http://example.com"]', '["https://example.com/path"]'],
            "REFRESH_COOKIE_HTTPONLY": ["false"],
            "REFRESH_COOKIE_SAMESITE": ["none"],
            "SMTP_PORT": ["0", "65536", "words"],
            "SMTP_SECURITY": ["none"],
            "SMTP_FROM_EMAIL": ["bad-email"],
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError) as error:
                    self.load(**{name: value})
                self.assertIn(name, str(error.exception))

    def test_production_cookie_and_https_safety(self):
        safe = dict(APP_ENV="production", FRONTEND_ORIGINS='["https://market.example.invalid"]')
        self.assertTrue(self.load(**safe).refresh_cookie_secure)
        for override in ({"REFRESH_COOKIE_SECURE": "false"}, {"FRONTEND_ORIGINS": '["http://localhost:5173"]'}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.load(**(safe | override))
        for mode in ("development", "test"):
            self.assertFalse(self.load(APP_ENV=mode, FRONTEND_ORIGINS='["http://127.0.0.1:5173"]', REFRESH_COOKIE_SECURE="false").refresh_cookie_secure)

    def test_smtp_optional_then_required_without_network(self):
        settings = self.load()
        with self.assertRaises(ValueError) as error:
            settings.validate_email_delivery()
        self.assertIn("SMTP_HOST", str(error.exception))
        configured = self.load(SMTP_HOST="smtp.example.invalid", SMTP_PORT="587", SMTP_USERNAME="TEST_LOGIN_MARKER", SMTP_PASSWORD="TEST_PASSWORD_MARKER", SMTP_FROM_EMAIL="test@example.invalid")
        self.assertIs(configured.validate_email_delivery(), configured)

    def test_secret_redaction_in_repr_and_errors(self):
        settings = self.load(SMTP_USERNAME="TEST_LOGIN_MARKER", SMTP_PASSWORD="TEST_PASSWORD_MARKER")
        representation = repr(settings)
        for marker in ("TEST_DB_MARKER", "TEST_ONLY_MARKER", "TEST_LOGIN_MARKER", "TEST_PASSWORD_MARKER"):
            self.assertNotIn(marker, representation)
        output = io.StringIO()
        bad_values = dict(DATABASE_URL="sqlite://TEST_DB_MARKER", JWT_SECRET_KEY="SECRET_BAD_MARKER")
        with contextlib.redirect_stderr(output):
            try:
                self.load(**bad_values)
            except ValueError:
                traceback.print_exc()
        self.assertIn("DATABASE_URL", output.getvalue())
        self.assertIn("JWT_SECRET_KEY", output.getvalue())
        self.assertNotIn("TEST_DB_MARKER", output.getvalue())
        self.assertNotIn("SECRET_BAD_MARKER", output.getvalue())

    def test_upload_path_does_not_depend_on_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(self.load(UPLOAD_DIR="backend/uploads").upload_dir, REPOSITORY_ROOT / "backend" / "uploads")
            finally:
                os.chdir(previous)
