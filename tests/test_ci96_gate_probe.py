"""Intentional failed-CI proof for issue96. Never merge this probe into main."""
import unittest


class DeliberateCIGateFailure(unittest.TestCase):
    def test_required_backend_failure_prevents_deployment(self):
        self.fail('Intentional isolated issue96 CI gate proof; do not merge.')
