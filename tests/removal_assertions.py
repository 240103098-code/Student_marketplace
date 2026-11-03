"""Test-only exact removal DTO assertions with aware timestamp semantics."""
from datetime import datetime


def assert_removed_response(case, actual, listing_id, published_at):
    case.assertIsInstance(actual, dict)
    case.assertEqual(set(actual), {'id', 'status', 'published_at'})
    case.assertIs(type(actual['id']), int)
    case.assertEqual(actual['id'], listing_id)
    case.assertEqual(actual['status'], 'removed')
    if published_at is None:
        case.assertIsNone(actual['published_at'])
        return

    def aware(value):
        case.assertIsInstance(value, str)
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            case.fail('Invalid publication timestamp')
        case.assertIsNotNone(parsed.tzinfo)
        case.assertIsNotNone(parsed.utcoffset())
        return parsed

    case.assertEqual(aware(actual['published_at']), aware(published_at))
