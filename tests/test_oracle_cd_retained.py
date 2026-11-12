"""Execute the emitted retention program with real configuration and guarded PG."""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import text

from backend.config import ConfigurationError, REPOSITORY_ROOT
from postgresql_support import open_disposable_database
from tools import oracle_cd as cd


TABLES = ('users', 'listings', 'listing_photos', 'refresh_sessions',
          'email_codes', 'categories', 'listing_reports')
JWT_MARKER = 'RETENTION_JWT_SENTINEL_' + 'a' * 48
IDENTITY_MARKER = 'retention-sentinel@sdu.edu.kz'


def emitted_program():
    """Capture exactly what Host sends to Python, replacing transport only."""
    captured = []
    host = cd.Host.__new__(cd.Host)
    def compose(*arguments):
        captured.append(arguments)
        return subprocess.CompletedProcess([], 0, b'', b'')
    host.compose = compose
    assert host.retained() == b''
    assert len(captured) == 1 and captured[0][:-1] == ('exec', '-T', 'app', 'python', '-c')
    return captured[0][-1]


def environment(database_url):
    return {'APP_ENV': 'production', 'DATABASE_URL': database_url,
            'JWT_SECRET_KEY': JWT_MARKER, 'FRONTEND_ORIGINS': '["https://retention.invalid"]',
            'REFRESH_COOKIE_SECURE': 'true', 'SMTP_HOST': 'mail.invalid', 'SMTP_PORT': '587',
            'SMTP_USERNAME': IDENTITY_MARKER, 'SMTP_PASSWORD': 'RETENTION_SMTP_SENTINEL',
            'SMTP_FROM_EMAIL': IDENTITY_MARKER, 'SMTP_SECURITY': 'starttls'}


def execute_program(program, configured, upload_root):
    # Map ONLY the fixed container filesystem root into an owned real fixture.
    # The emitted loader and SQL run unchanged; no copied settings expression.
    mapped = ast.parse(program)
    roots = [node for node in ast.walk(mapped)
             if isinstance(node, ast.Constant) and node.value == '/data/uploads']
    assert len(roots) == 1
    roots[0].value = str(upload_root)
    output = io.StringIO()
    namespace = {}
    try:
        with patch.dict(os.environ, configured, clear=True), \
             patch('backend.config.dotenv_values', side_effect=AssertionError('Unexpected env-file access')), \
             patch('socket.create_connection', side_effect=AssertionError('Unexpected SMTP/network helper')), \
             contextlib.redirect_stdout(output):
            exec(compile(ast.fix_missing_locations(mapped), '<actual-retention-program>', 'exec'), namespace)
    finally:
        # The real transport is a short-lived Python process. Model its resource
        # exit here so in-process tests do not retain transaction/schema locks.
        if 'c' in namespace:
            namespace['c'].close()
        if 'e' in namespace:
            namespace['e'].dispose()
    return output.getvalue().encode()


class RetentionConfiguration(unittest.TestCase):
    def test_missing_or_invalid_environment_fails_before_any_database_connection(self):
        valid = environment('postgresql+psycopg://synthetic:DB_SENTINEL@127.0.0.1/retention')
        variants = [valid | {'JWT_SECRET_KEY': ''}, valid | {'JWT_SECRET_KEY': 'too-short'},
                    {key: value for key, value in valid.items() if key != 'JWT_SECRET_KEY'},
                    {key: value for key, value in valid.items() if key != 'DATABASE_URL'},
                    valid | {'DATABASE_URL': 'INVALID_DATABASE_SENTINEL'},
                    valid | {'SMTP_PORT': 'INVALID_SMTP_SENTINEL'},
                    valid | {'FRONTEND_ORIGINS': 'INVALID_ORIGIN_SENTINEL'}]
        with tempfile.TemporaryDirectory() as root:
            for configured in variants:
                with self.subTest(case=variants.index(configured)), \
                     patch('sqlalchemy.create_engine') as connect, \
                     self.assertRaises((ConfigurationError, ValidationError)):
                    execute_program(emitted_program(), configured, Path(root))
                connect.assert_not_called()

    def test_real_configuration_failure_stays_sanitized_at_controller_public_boundary(self):
        configured = environment('postgresql+psycopg://synthetic:DB_SENTINEL@127.0.0.1/retention')
        configured['JWT_SECRET_KEY'] = 'INVALID_JWT_SENTINEL'
        try:
            with tempfile.TemporaryDirectory() as root:
                execute_program(emitted_program(), configured, Path(root))
        except (ConfigurationError, ValidationError) as error:
            native = subprocess.CompletedProcess(['PRIVATE_COMMAND_SENTINEL'], 1,
                ('PRIVATE_STDOUT_SENTINEL ' + IDENTITY_MARKER).encode(),
                (str(error) + ' RETENTION_SMTP_SENTINEL DB_SENTINEL').encode())
        else:
            self.fail('Invalid real configuration unexpectedly produced a snapshot')
        public = io.StringIO()
        def operation(_request):
            return cd.execute(['PRIVATE_COMMAND_SENTINEL', JWT_MARKER])
        with patch.object(cd, 'controller', side_effect=operation), \
             patch.object(cd.subprocess, 'run', return_value=native), \
             patch.object(cd.sys, 'argv', ['controller']), \
             patch.object(cd.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'probe'))), \
             contextlib.redirect_stdout(public):
            self.assertEqual(cd.main(), 1)
        self.assertEqual(json.loads(public.getvalue()), {'result': 'FAIL', 'stage': 'subprocess-failed'})
        for sentinel in ('SENTINEL', IDENTITY_MARKER, JWT_MARKER, 'ValidationError', 'JWT_SECRET_KEY'):
            self.assertNotIn(sentinel, public.getvalue())


class RetentionPostgreSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        configuration = Config(str(REPOSITORY_ROOT / 'alembic.ini'))
        configuration.attributes['settings'] = cls.settings
        cls.addClassCleanup(command.downgrade, configuration, 'base')
        command.upgrade(configuration, 'head')
        with cls.database.engine.begin() as connection:
            uid = connection.execute(text("INSERT INTO users(email,password_hash,verified) VALUES "
                "(:email,'ROW_PASSWORD_SENTINEL',true) RETURNING id"), {'email': IDENTITY_MARKER}).scalar_one()
            listing = connection.execute(text("INSERT INTO listings(owner_id,category_id,title,description,price,condition,status) "
                "VALUES (:uid,1,'Retention fixture','Synthetic retention description',10,'used','pending') RETURNING id"),
                {'uid': uid}).scalar_one()
            cls.relative = f'listings/{listing}/' + 'a' * 32 + '.png'
            connection.execute(text("INSERT INTO listing_photos(listing_id,storage_path,position) VALUES (:id,:path,1)"),
                {'id': listing, 'path': cls.relative})
            connection.execute(text("INSERT INTO email_codes(user_id,purpose,digest,expires_at) "
                "VALUES (:uid,'registration','ROW_CODE_SENTINEL',now()+interval '1 hour')"), {'uid': uid})
            connection.execute(text("INSERT INTO refresh_sessions(user_id,token_digest,expires_at) "
                "VALUES (:uid,'ROW_REFRESH_SENTINEL',now()+interval '1 day')"), {'uid': uid})
            connection.execute(text("INSERT INTO listing_reports(reporter_id,listing_id,reason) VALUES (:uid,:listing,'spam')"),
                {'uid': uid, 'listing': listing})

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = self.root / self.relative
        self.image.parent.mkdir(parents=True)
        Image.new('RGB', (2, 2), (60, 90, 120)).save(self.image, format='PNG')
        self.configured = environment(self.settings.database_url.get_secret_value())

    def database_rows(self):
        with self.database.engine.connect() as connection:
            return {table: sorted(connection.execute(text('SELECT row_to_json(x)::text FROM ' + table + ' x')).scalars())
                    for table in TABLES}

    def snapshot(self):
        return execute_program(emitted_program(), self.configured, self.root)

    def test_actual_program_uses_real_loader_pg_tables_and_image_without_mutation(self):
        before = self.database_rows()
        self.assertTrue(all(before[table] for table in TABLES))
        content = self.image.read_bytes()
        first = self.snapshot()
        self.assertEqual(first, self.snapshot())
        result = json.loads(first)
        self.assertEqual(set(result), {'db', 'files'})
        self.assertEqual(result['db'], {table: hashlib.sha256('\n'.join(before[table]).encode()).hexdigest()
                                      for table in TABLES})
        self.assertEqual(result['files'], [[str(Path(self.relative)), hashlib.sha256(content).hexdigest()]])
        self.assertEqual(self.database_rows(), before)
        self.assertEqual(self.image.read_bytes(), content)
        for sentinel in ('ROW_', 'SENTINEL', IDENTITY_MARKER, JWT_MARKER):
            self.assertNotIn(sentinel, first.decode())

    def test_relative_path_and_exact_image_bytes_both_affect_snapshot(self):
        before = self.database_rows()
        original = self.image.read_bytes()
        baseline = self.snapshot()
        moved = self.image.with_name('b' * 32 + '.png')
        self.image.rename(moved)
        self.assertNotEqual(self.snapshot(), baseline)
        moved.rename(self.image)
        self.image.write_bytes(original + b'changed')
        self.assertNotEqual(self.snapshot(), baseline)
        self.image.write_bytes(original)
        self.assertEqual(self.snapshot(), baseline)
        self.assertEqual(self.database_rows(), before)

    def test_upload_symlink_rejection_is_not_replaced_with_empty_data(self):
        # A fixture path's link flag is portable; real PG/configuration still run.
        with patch.object(Path, 'is_symlink', return_value=True), self.assertRaises(AssertionError):
            self.snapshot()
