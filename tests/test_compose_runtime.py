"""Compose health boundaries and sanitized bounded startup failures."""
import asyncio
from contextlib import redirect_stdout
import io
import threading
import unittest
from unittest.mock import patch

from backend.compose_runtime import Readiness, main
from backend.config import load_settings


def settings():
    return load_settings(environ={'APP_ENV':'test','JWT_SECRET_KEY':'TEST_ONLY_'+'x'*48,'DATABASE_URL':'postgresql+psycopg://private:private@127.0.0.1/test'},env_file=None)


class ReadinessTest(unittest.IsolatedAsyncioTestCase):
    async def test_probe_slots_bound_work_without_blocking_the_event_loop(self):
        probe=Readiness(settings());self.addCleanup(probe.close)
        release=threading.Event()
        def unavailable(*args,**kwargs):
            release.wait(1)
            raise RuntimeError('Sensitive driver context must not escape')
        with patch('backend.compose_runtime.psycopg.connect',side_effect=unavailable):
            first=asyncio.create_task(probe.ready());second=asyncio.create_task(probe.ready())
            await asyncio.sleep(.03)
            self.assertFalse(await asyncio.wait_for(probe.ready(),.1))
            release.set()
            self.assertEqual(await asyncio.gather(first,second),[False,False])

    async def test_probe_is_readonly_checks_head_and_recovers_after_failure(self):
        from unittest.mock import MagicMock
        probe=Readiness(settings());self.addCleanup(probe.close)
        connection=MagicMock();connection.__enter__.return_value=connection
        connection.execute.return_value.fetchall.return_value=[('0003_listings',)]
        with patch('backend.compose_runtime.psycopg.connect',return_value=connection) as connect:
            self.assertTrue(await probe.ready())
            self.assertEqual(connect.call_args.kwargs['connect_timeout'],2)
            self.assertIn('default_transaction_read_only=on',connect.call_args.kwargs['options'])
            connection.execute.return_value.fetchall.return_value=[('unprepared',)]
            self.assertFalse(await probe.ready())
            connection.execute.return_value.fetchall.return_value=[('0003_listings',)]
            self.assertTrue(await probe.ready())


class ComposeCommandTest(unittest.TestCase):
    def test_migration_is_bounded_and_failures_are_sanitized(self):
        output=io.StringIO()
        with patch('backend.compose_runtime.postgres_settings'),patch('backend.compose_runtime.subprocess.run') as run,redirect_stdout(output):
            run.return_value.returncode=1
            self.assertEqual(main(['migrate']),1)
            self.assertTrue(run.call_args.kwargs['capture_output'])
            self.assertEqual(run.call_args.kwargs['timeout'],60)
        self.assertEqual(output.getvalue(),'Compose operation failed; verify private configuration, database health and migration state.\n')

    def test_compose_serve_refuses_sqlite_before_server_start(self):
        sqlite=load_settings(environ={'JWT_SECRET_KEY':'TEST_ONLY_'+'x'*48},env_file=None)
        with patch('backend.compose_runtime.load_settings',return_value=sqlite),patch('uvicorn.run') as serve,redirect_stdout(io.StringIO()):
            self.assertEqual(main(['serve']),1)
            serve.assert_not_called()
