"""Regress UTC wire-format portability without relaxing the removal contract."""
import unittest
from tests.removal_assertions import assert_removed_response


class RemovalTimestampAssertions(unittest.TestCase):
    def response(self, timestamp):
        return {'id': 7, 'status': 'removed', 'published_at': timestamp}

    def test_equivalent_aware_rfc3339_instants_pass(self):
        for timestamp in ('2026-10-12T12:00:00Z', '2026-10-12T12:00:00+00:00', '2026-10-12T17:00:00+05:00'):
            with self.subTest(timestamp=timestamp):
                assert_removed_response(self, self.response(timestamp), 7, '2026-10-12T12:00:00Z')

    def test_different_instants_fail(self):
        for timestamp in ('2026-10-12T12:00:01Z', '2026-10-12T12:00:00.000001Z', '2026-10-12T12:00:00+05:00'):
            with self.subTest(timestamp=timestamp), self.assertRaises(AssertionError):
                assert_removed_response(self, self.response(timestamp), 7, '2026-10-12T12:00:00Z')

    def test_null_is_exact_in_both_directions(self):
        assert_removed_response(self, self.response(None), 7, None)
        for actual, expected in ((None, '2026-10-12T12:00:00Z'), ('2026-10-12T12:00:00Z', None)):
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                assert_removed_response(self, self.response(actual), 7, expected)

    def test_invalid_or_timezone_naive_values_fail(self):
        for timestamp in ('not-a-time', '2026-10-12T12:00:00', '2026-10-12', '2026-10-12T12:00:00+25:00', 42):
            with self.subTest(timestamp=timestamp), self.assertRaises(AssertionError):
                assert_removed_response(self, self.response(timestamp), 7, '2026-10-12T12:00:00Z')
        with self.assertRaises(AssertionError):
            assert_removed_response(self, self.response('2026-10-12T12:00:00Z'), 7, '2026-10-12T12:00:00')

    def test_fields_id_and_status_remain_exact(self):
        valid=self.response(None)
        for response in (valid | {'unexpected': True}, {key:value for key,value in valid.items() if key!='published_at'}, valid | {'id':8}, valid | {'id':True}, valid | {'status':'active'}):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                assert_removed_response(self, response, 7, None)
