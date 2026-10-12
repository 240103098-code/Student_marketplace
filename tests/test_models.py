import subprocess
import sys
import unittest

from backend.config import REPOSITORY_ROOT
from backend.models import EmailCode, RefreshSession, User


class ModelRepresentationTest(unittest.TestCase):
    def test_sensitive_digests_are_absent_from_repr(self):
        objects = [User(password_hash="SENSITIVE_PASSWORD_MARKER"), EmailCode(digest="SENSITIVE_CODE_MARKER"), RefreshSession(token_digest="SENSITIVE_REFRESH_MARKER")]
        for item in objects:
            self.assertNotIn("SENSITIVE_", repr(item))

    def test_model_import_does_not_load_settings_or_connect(self):
        result = subprocess.run([
            sys.executable, "-c",
            "from unittest.mock import patch;\nwith patch('backend.config.load_settings', side_effect=AssertionError), patch('sqlalchemy.create_engine', side_effect=AssertionError):\n import backend.models; assert len(backend.models.Base.metadata.tables) == 3",
        ], cwd=REPOSITORY_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
