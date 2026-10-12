import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import REPOSITORY_ROOT, load_settings


class ApplicationFactoryTest(unittest.TestCase):
    def settings(self):
        return load_settings(environ={"DATABASE_URL": "postgresql://test_user@localhost/test_database", "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40}, env_file=None)

    def test_import_is_independent_of_settings_and_connections(self):
        result = subprocess.run([sys.executable, "-c", "from unittest.mock import patch;\nwith patch('backend.config.load_settings', side_effect=AssertionError), patch('sqlalchemy.create_engine', side_effect=AssertionError):\n import backend.main"], cwd=REPOSITORY_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_owned_resources_dispose_on_shutdown_borrowed_resources_do_not(self):
        with patch("backend.app.Database") as factory:
            app = create_app(self.settings())
            with TestClient(app):
                factory.return_value.dispose.assert_not_called()
            factory.return_value.dispose.assert_called_once()
        borrowed = Mock()
        with TestClient(create_app(self.settings(), borrowed)):
            pass
        borrowed.dispose.assert_not_called()
