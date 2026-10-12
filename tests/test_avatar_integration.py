from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.images import ImageStorage, ImageStorageError, MAX_BYTES, canonical_image
from backend.models import User
from postgresql_support import open_disposable_database


def picture(format='PNG', size=(8, 8), exif=None):
    out = BytesIO()
    Image.new('RGB', size, 'green').save(out, format=format, **({'exif': exif} if exif else {}))
    return out.getvalue()


class AvatarPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT / 'alembic.ini'))
        cls.configuration.attributes['settings'] = cls.settings
        command.upgrade(cls.configuration, 'head')
        cls.addClassCleanup(command.downgrade, cls.configuration, '0001_baseline')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='avatar-disposable-')
        self.root = Path(self.temp.name)/'uploads'
        self.settings = self.settings.model_copy(update={'upload_dir': self.root})
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.context = TestClient(create_app(self.settings, self.database, clock=lambda: self.now))
        self.client = self.context.__enter__()
        with self.database.session() as session:
            self.user = User(email='student@sdu.edu.kz', password_hash=PasswordHasher().hash('TEST_AVATAR_PASSWORD_123'), verified=True)
            self.other = User(email='other@sdu.edu.kz', password_hash=PasswordHasher().hash('TEST_AVATAR_PASSWORD_123'), verified=True)
            session.add_all([self.user, self.other]); session.flush()
        self.headers = {'Authorization': 'Bearer '+self.login(self.user.email)}
        self.other_headers = {'Authorization': 'Bearer '+self.login(self.other.email)}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        with self.database.session() as session: session.execute(delete(User))
        self.temp.cleanup()

    def login(self, email):
        return self.client.post('/auth/login', json={'email': email, 'password': 'TEST_AVATAR_PASSWORD_123'}).json()['access_token']

    def upload(self, raw=None, **kwargs):
        return self.client.post('/users/me/avatar', files={'image': ('../../SENSITIVE_ORIGINAL.svg', picture() if raw is None else raw, 'image/svg+xml')}, headers=self.headers, **kwargs)

    def path(self, user_id=None):
        with self.database.session() as session: return session.get(User, self.user.id if user_id is None else user_id).avatar_path

    def test_formats_private_read_generated_paths_and_metadata_stripping(self):
        exif = Image.Exif(); exif[270] = 'SENSITIVE_EXIF_MARKER'
        for format, media in [('JPEG','image/jpeg'), ('PNG','image/png'), ('WEBP','image/webp')]:
            result = self.upload(picture(format, exif=exif))
            self.assertEqual(result.status_code, 200)
            self.assertNotIn('SENSITIVE', result.text)
            relative = self.path()
            self.assertRegex(relative, rf'^avatars/{self.user.id}/[0-9a-f]{{32}}\.(jpg|png|webp)$')
            read = self.client.get('/users/me/avatar', headers=self.headers)
            self.assertEqual(read.status_code, 200)
            self.assertEqual(read.headers['content-type'], media)
            self.assertEqual(read.headers['cache-control'], 'private, no-store')
            self.assertNotIn(b'SENSITIVE_EXIF', read.content)
            with Image.open(BytesIO(read.content)) as decoded:
                self.assertEqual(decoded.size, (8,8))
                self.assertEqual(dict(decoded.getexif()), {})
        self.assertEqual(len(list(self.root.rglob('*.*'))), 1)

    def test_replacement_removal_idempotence_and_other_account_file_isolation(self):
        self.upload(); first = self.root/self.path()
        other = self.client.post('/users/me/avatar', files={'image': ('other.png',picture(),'image/png')}, headers=self.other_headers)
        self.assertEqual(other.status_code, 200)
        other_path = self.root/self.path(self.other.id)
        other_bytes = other_path.read_bytes()
        self.upload(picture('JPEG'))
        self.assertFalse(first.exists())
        latest = self.root/self.path()
        result = self.client.delete('/users/me/avatar', headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(latest.exists()); self.assertIsNone(self.path())
        self.assertEqual(self.client.delete('/users/me/avatar', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/users/me/avatar', headers=self.headers).status_code, 404)
        self.assertEqual(other_path.read_bytes(), other_bytes)

    def test_byte_pixel_and_decompression_limits(self):
        small = picture()
        self.assertEqual(self.upload(small + bytes(MAX_BYTES-len(small))).status_code, 200)
        self.assertEqual(self.upload(small + bytes(MAX_BYTES+1-len(small))).status_code, 413)
        self.assertEqual(self.upload(picture(size=(5000,4000))).status_code, 200)
        self.assertEqual(self.upload(picture(size=(5000,4001))).status_code, 400)
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 1):
            self.assertEqual(self.upload(picture(size=(2,1))).status_code, 400)

    def test_malformed_unsupported_and_strict_multipart_leave_previous_intact(self):
        self.upload(); previous = self.path(); content = (self.root/previous).read_bytes()
        for raw in [b'<svg/>', b'NOT_AN_IMAGE', picture()[:30], picture('JPEG')[:-50], picture('GIF')]:
            self.assertEqual(self.upload(raw).status_code, 400)
            self.assertEqual(self.path(), previous)
        for files, data in [([('image',('a.png',picture())),('image',('b.png',picture()))],None), ({'wrong': ('a.png',picture())},None), ({'image':('a.png',picture())},{'user_id':str(self.other.id)})]:
            self.assertEqual(self.client.post('/users/me/avatar', files=files, data=data, headers=self.headers).status_code, 400)
        self.assertEqual((self.root/previous).read_bytes(), content)

    def test_failed_commit_cleans_new_file_and_preserves_previous_avatar(self):
        self.upload(); previous = self.path(); original = Session.commit
        def fail_changed(session):
            user = session.get(User, self.user.id)
            if user and user.avatar_path != previous: raise SQLAlchemyError('SENSITIVE_DRIVER')
            return original(session)
        with patch.object(Session, 'commit', fail_changed):
            result = self.upload(picture('JPEG'))
        self.assertEqual(result.status_code, 500)
        self.assertNotIn('SENSITIVE', result.text)
        self.assertEqual(self.path(), previous)
        self.assertEqual(len(list(self.root.rglob('*.*'))),1)
        self.assertTrue((self.root/previous).is_file())
        with patch.object(Session, 'commit', fail_changed):
            self.assertEqual(self.client.delete('/users/me/avatar', headers=self.headers).status_code, 500)
        self.assertTrue((self.root/previous).is_file())

    def test_filesystem_failure_and_postcommit_cleanup_failure_are_honest(self):
        self.upload(); previous = self.path()
        with patch.object(ImageStorage, 'write', side_effect=ImageStorageError('SENSITIVE_PATH')):
            self.assertEqual(self.upload().status_code, 500)
        self.assertEqual(self.path(), previous)
        with patch.object(ImageStorage, 'delete', side_effect=ImageStorageError('SENSITIVE_CLEANUP')):
            result = self.upload(picture('JPEG'))
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['cleanup_pending'])
        self.assertNotEqual(self.path(),previous)
        self.assertTrue((self.root/previous).is_file())

    def test_ownership_traversal_and_real_symlink_or_junction_escape(self):
        self.upload()
        outside = Path(self.temp.name)/'outside'; outside.mkdir()
        marker = outside/'keep.txt'; marker.write_text('preserve')
        for path in ['../outside/keep.txt', str(marker), f'avatars/{self.other.id}/{uuid.uuid4().hex}.png']:
            with self.database.session() as session: session.get(User,self.user.id).avatar_path = path
            self.assertEqual(self.client.get('/users/me/avatar',headers=self.headers).status_code,500)
            self.assertEqual(self.client.delete('/users/me/avatar',headers=self.headers).status_code,500)
        self.assertEqual(marker.read_text(),'preserve')
        with self.database.session() as session: session.get(User,self.user.id).avatar_path = None
        folder = self.root/'avatars'/str(self.user.id)
        for file in folder.iterdir(): file.unlink()
        folder.rmdir()
        try:
            os.symlink(outside,folder,target_is_directory=True)
        except OSError:
            escaped_path = str(folder).replace("'","''"); escaped_target = str(outside).replace("'","''")
            subprocess.run(['powershell','-NoProfile','-Command',f"New-Item -ItemType Junction -Path '{escaped_path}' -Target '{escaped_target}' | Out-Null"],check=True,capture_output=True)
        try:
            self.assertEqual(self.upload().status_code,500)
            self.assertEqual(marker.read_text(),'preserve')
        finally:
            if folder.is_symlink(): folder.unlink()
            else: folder.rmdir()  # Remove only the junction, never its target.

    def test_missing_ineligible_and_revoked_access_cannot_read_or_mutate(self):
        self.assertEqual(self.client.get('/users/me/avatar').status_code,401)
        self.assertEqual(self.client.post('/users/me/avatar',files={'image':('x.png',picture())}).status_code,401)
        self.assertEqual(self.client.delete('/users/me/avatar').status_code,401)
        self.assertEqual(self.client.get('/users/me/avatar',headers=self.headers).status_code,404)
        self.upload()
        with self.database.session() as session: session.get(User,self.user.id).suspended=True
        self.assertEqual(self.client.get('/users/me/avatar',headers=self.headers).status_code,401)
        self.assertEqual(self.upload().status_code,401)
        self.assertEqual(self.client.delete('/users/me/avatar',headers=self.headers).status_code,401)
