"""Deliberately red CI gate proof. Probe branch only; never merge this file."""
import unittest

class RequiredGateProbe(unittest.TestCase):
    def test_required_gate_rejects_a_genuine_failed_test(self):
        self.assertFalse(True, 'Intentional isolated probe: the required CI gate must fail.')
