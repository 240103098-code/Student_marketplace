"""Actual offline SQLite→guarded PostgreSQL data, file and credential continuity."""
from contextlib import closing
from datetime import timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from backend.app import create_app
from backend.config import REPOSITORY_ROOT, load_settings
from backend.database import Database
from backend.email_codes import code_digest, utc_now
from backend.images import ImageStorage, canonical_image
from backend.migrate_storage import migrate, source_snapshot, rows_from, row_digest, digest_bytes, MigrationError, copy_manifest, verify_migration
from backend.models import User, EmailCode, RefreshSession, Listing, ListingPhoto, ListingReport
from postgresql_support import open_disposable_database
from test_avatar_integration import picture

PASSWORD='DISPOSABLE_MIGRATION_PASSWORD_123'
SECRET='TEST_ONLY_MIGRATION_'+ 'x'*48

class StorageMigrationPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pgsettings,cls.pg,_=open_disposable_database();cls.addClassCleanup(cls.pg.dispose)
        cls.cfg=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.cfg.attributes['settings']=cls.pgsettings
        command.upgrade(cls.cfg,'head');cls.addClassCleanup(command.downgrade,cls.cfg,'0001_baseline')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='marketplace-migration-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'offline.sqlite3';self.uploads=self.root/'source-uploads';self.uploads.mkdir()
        self.destination=self.root/'destination-uploads';self.backup=self.root/'backup'
        self.settings=load_settings(environ={'APP_ENV':'test','DATABASE_URL':'sqlite+pysqlite:///'+str(self.source),'UPLOAD_DIR':str(self.uploads),'JWT_SECRET_KEY':SECRET,'FRONTEND_ORIGINS':'["http://127.0.0.1"]'},env_file=None)
        cfg=Config(str(REPOSITORY_ROOT/'alembic-sqlite.ini'));cfg.attributes['settings']=self.settings;command.upgrade(cfg,'head')
        db=Database(self.settings);now=utc_now();self.now=now
        image=canonical_image(picture());self.image=image.data
        avatar=ImageStorage(self.uploads).write(image,10);self.avatar=avatar
        self.photo=ImageStorage(self.uploads,'listings').write(image,101)
        with db.session() as session:
            for id,email,verified,suspended,role in [(10,'owner',True,False,'student'),(20,'buyer',True,False,'student'),(30,'unverified',False,False,'student'),(40,'suspended',True,True,'student'),(50,'admin',True,False,'admin')]:
                session.add(User(id=id,email=email+'@sdu.edu.kz',password_hash=PasswordHasher().hash(PASSWORD),verified=verified,suspended=suspended,role=role,created_at=now,name='Synthetic student',phone='+77001234567',telegram_username='valid_name',external_contact_url='https://example.invalid/contact',avatar_path=avatar if id==10 else None))
            session.flush()
            for offset,state in enumerate(['active','pending','sold','rejected','removed']):
                session.add(Listing(id=101+offset,owner_id=10,category_id=1,title='Migration synthetic item',description='A private disposable item.',price=Decimal('1000000000.00') if offset==0 else Decimal('0.01'),currency='KZT',condition='used',status=state,created_at=now.astimezone(timezone(timedelta(hours=5))),published_at=now if state in {'active','sold','removed'} else None,rejection_reason='Not suitable' if state=='rejected' else None))
            session.flush()
            session.add(ListingPhoto(id=201,listing_id=101,storage_path=self.photo,position=1))
            session.add_all([ListingReport(id=301,reporter_id=20,listing_id=101,reason='spam',created_at=now),ListingReport(id=302,reporter_id=20,listing_id=105,reason='misleading_information',created_at=now,reviewed_at=now)])
            session.add_all([EmailCode(id=401,user_id=30,purpose='registration',digest=code_digest(self.settings,30,'registration','123456'),created_at=now,expires_at=now+timedelta(minutes=10),wrong_attempts=2),EmailCode(id=402,user_id=10,purpose='password_reset',digest='historical-disposable-digest',created_at=now-timedelta(days=1),expires_at=now-timedelta(hours=23),wrong_attempts=5,consumed_at=now-timedelta(hours=23),invalidated_at=now-timedelta(hours=23))])
        with TestClient(create_app(self.settings,db),base_url='http://127.0.0.1') as client:
            token=client.post('/auth/login',json={'email':'owner@sdu.edu.kz','password':PASSWORD});self.assertEqual(token.status_code,200)
            csrf=client.get('/auth/csrf').json()['csrf_token']
            result=client.post('/auth/refresh',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':csrf});self.assertEqual(result.status_code,200)
            self.access=result.json()['access_token'];self.refresh=client.cookies.get('refresh_token');self.csrf=client.get('/auth/csrf').json()['csrf_token']
        db.dispose() # checkpoint/close all owned handles; no sidecars permitted.
        self.before=digest_bytes(self.source)
        with source_snapshot(self.source) as (c,_,_):self.original={name:row_digest(rows) for name,rows in rows_from(c).items()}

    def tearDown(self):
        with self.pg.session() as session:session.execute(delete(User))
        # Test-created unexpected schema objects only; never migration-tool cleanup.
        with self.pg.engine.begin() as c:c.exec_driver_sql('DROP TABLE IF EXISTS migration_test_extra')

    def run_migration(self,**overrides):
        return migrate(source=self.source,source_uploads=self.uploads,target_url=self.pgsettings.database_url.get_secret_value(),destination_uploads=self.destination,backup=self.backup,execute=True,confirm_source=self.source.name,confirm_target=self.pg.engine.url.database,quiesced=True,**overrides)

    def assert_empty(self):
        with self.pg.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(User)),0)

    def test_populated_all_tables_backup_sequences_and_real_api_security_continuity(self):
        result=self.run_migration();self.assertEqual(result['status'],'committed-and-verified')
        self.assertEqual(digest_bytes(self.source),self.before)
        with self.pg.engine.connect() as c:self.assertEqual({name:row_digest(rows) for name,rows in rows_from(c).items()},self.original)
        with source_snapshot(self.backup/'source.sqlite3') as (c,_,_):self.assertEqual({name:row_digest(rows) for name,rows in rows_from(c).items()},self.original)
        self.assertEqual((self.backup/'uploads'/self.photo).read_bytes(),self.image)
        restored=self.root/'restored.sqlite3';restored.write_bytes((self.backup/'source.sqlite3').read_bytes())
        restoredsettings=load_settings(environ={'APP_ENV':'test','DATABASE_URL':'sqlite+pysqlite:///'+str(restored),'UPLOAD_DIR':str(self.backup/'uploads'),'JWT_SECRET_KEY':SECRET},env_file=None)
        with TestClient(create_app(restoredsettings)) as restoredclient:
            self.assertEqual(restoredclient.get('/auth/me',headers={'Authorization':'Bearer '+self.access}).status_code,200)
            self.assertEqual(restoredclient.get('/users/me/avatar',headers={'Authorization':'Bearer '+self.access}).content,self.image)
        targetsettings=self.pgsettings.model_copy(update={'jwt_secret_key':self.settings.jwt_secret_key,'upload_dir':self.destination,'frontend_origins':['http://127.0.0.1']})
        with TestClient(create_app(targetsettings,self.pg),base_url='http://127.0.0.1') as client:
            auth={'Authorization':'Bearer '+self.access}
            self.assertEqual(client.get('/auth/me',headers=auth).status_code,200)
            client.cookies.set('refresh_token',self.refresh,path='/auth')
            self.assertEqual(client.post('/auth/refresh',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':self.csrf}).status_code,200)
            owner=client.post('/auth/login',json={'email':'owner@sdu.edu.kz','password':PASSWORD});self.assertEqual(owner.status_code,200)
            ownerauth={'Authorization':'Bearer '+owner.json()['access_token']}
            self.assertEqual(client.get('/users/me/avatar',headers=ownerauth).content,self.image)
            self.assertEqual(client.get('/listings/101/photos/201',headers=ownerauth).content,self.image)
            self.assertEqual(client.get('/users/me/avatar').status_code,401)
            buyer=client.post('/auth/login',json={'email':'buyer@sdu.edu.kz','password':PASSWORD});buyerauth={'Authorization':'Bearer '+buyer.json()['access_token']}
            self.assertEqual(client.get('/users/me/avatar',headers=buyerauth).status_code,404)
            self.assertEqual(client.get('/listings/101/photos/201',headers=buyerauth).content,self.image)
            self.assertEqual(client.post('/auth/login',json={'email':'suspended@sdu.edu.kz','password':PASSWORD}).status_code,401)
            self.assertEqual(client.post('/auth/verify-email',json={'email':'unverified@sdu.edu.kz','code':'123456'}).status_code,200)
        with self.pg.session() as session:
            new=User(email='new@sdu.edu.kz',password_hash='not-an-auth-fixture',verified=False);session.add(new);session.flush();self.assertGreater(new.id,50)
        with self.pg.engine.begin() as c:
            for name,maximum in [('email_codes',402),('listings',105),('listing_photos',201),('listing_reports',302)]:
                self.assertGreater(c.scalar(text("SELECT nextval('"+name+"_id_seq')")),maximum)

    def test_dry_run_writes_nothing_and_refuses_missing_quiescence(self):
        before={str(p.relative_to(self.root)):digest_bytes(p) for p in self.root.rglob('*') if p.is_file()}
        args=dict(source=self.source,source_uploads=self.uploads,target_url=self.pgsettings.database_url.get_secret_value(),destination_uploads=self.destination,backup=self.backup)
        with self.assertRaises(MigrationError):migrate(**args)
        result=migrate(**args,quiesced=True);self.assertEqual(result['mode'],'dry-run')
        self.assertEqual(before,{str(p.relative_to(self.root)):digest_bytes(p) for p in self.root.rglob('*') if p.is_file()});self.assert_empty()

    def test_known_precommit_failures_clean_only_owned_files_keep_backup_and_source(self):
        for point in ('backup','database','published'):
            with self.subTest(point=point):
                def failure(stage):
                    if stage==point:raise RuntimeError('Injected disposable migration failure')
                with self.assertRaises(RuntimeError):self.run_migration(_fault=failure)
                self.assert_empty();self.assertFalse(self.destination.exists());self.assertEqual(digest_bytes(self.source),self.before)
                self.assertTrue((self.backup/'source.sqlite3').exists())
                # Each retry uses a NEW private backup; no overwrite/reuse.
                self.backup=self.root/('backup-after-'+point)

    def test_partial_file_failure_preserves_source_backup_and_empty_target(self):
        calls=[]
        def fail_partial(origin,target,manifest):
            calls.append(target)
            if len(calls)==2:
                copy_manifest(origin,target,manifest[:1]);raise OSError('Injected file failure')
            return copy_manifest(origin,target,manifest)
        with patch('backend.migrate_storage.copy_manifest',side_effect=fail_partial):
            with self.assertRaises(OSError):self.run_migration()
        self.assert_empty();self.assertFalse(self.destination.exists());self.assertEqual(digest_bytes(self.source),self.before)
        self.assertEqual(json.loads((self.backup/'recovery.json').read_text())['state'],'rolled-back-owned-files-cleaned')

    def test_commit_acknowledgment_failure_preserves_published_files_for_reconciliation(self):
        def ambiguous(stage):
            if stage=='commit-acknowledgment':raise ConnectionError('Simulated lost commit acknowledgment')
        with self.assertRaises(ConnectionError):self.run_migration(_fault=ambiguous)
        self.assertTrue(self.destination.exists());self.assertEqual((self.destination/self.photo).read_bytes(),self.image)
        verified=verify_migration(backup=self.backup,target_url=self.pgsettings.database_url.get_secret_value(),destination_uploads=self.destination,quiesced=True)
        self.assertEqual(verified['status'],'committed-and-verified')
        self.assertEqual(json.loads((self.backup/'recovery.json').read_text())['state'],'commit-outcome-unknown-reconciliation-required')
        with self.pg.session() as s:self.assertEqual(s.scalar(select(func.count()).select_from(User)),5)
        with self.assertRaises(MigrationError):self.run_migration()

    def test_nonempty_target_existing_destination_and_unexpected_schema_refused(self):
        with self.pg.session() as s:s.add(User(email='existing@sdu.edu.kz',password_hash='preserve-existing'))
        with self.assertRaises(MigrationError):self.run_migration()
        self.assertFalse(self.backup.exists())
        with self.pg.session() as s:s.execute(delete(User))
        with self.pg.engine.begin() as c:c.exec_driver_sql('CREATE TABLE migration_test_extra(id integer)')
        with self.assertRaises(MigrationError):self.run_migration()
        self.assertFalse(self.backup.exists())
        self.destination.mkdir();(self.destination/'unowned').write_text('preserve')
        with self.assertRaises(MigrationError):self.run_migration()
        self.assertEqual((self.destination/'unowned').read_text(),'preserve')

    def test_source_schema_sidecars_missing_unsafe_and_changed_images_refused(self):
        sidecar=Path(str(self.source)+'-wal');sidecar.write_bytes(b'Uncheckpointed or unsafe WAL')
        with self.assertRaises(MigrationError):self.run_migration()
        self.assertEqual(sidecar.read_bytes(),b'Uncheckpointed or unsafe WAL');sidecar.unlink()
        with closing(sqlite3.connect(self.source,isolation_level=None)) as c:c.execute('CREATE TABLE unexpected(id integer)')
        with self.assertRaises(MigrationError):self.run_migration()
        with closing(sqlite3.connect(self.source,isolation_level=None)) as c:c.execute('DROP TABLE unexpected')
        missing=self.uploads/self.photo;saved=missing.read_bytes();missing.unlink()
        with self.assertRaises(Exception):self.run_migration()
        missing.write_bytes(saved)
        def mutate(stage):
            if stage=='backup':missing.write_bytes(b'changed after manifest')
        with self.assertRaises(MigrationError):self.run_migration(_fault=mutate)
        self.assert_empty();self.assertFalse(self.destination.exists())
        self.assertEqual((self.backup/'uploads'/self.photo).read_bytes(),saved)

    def test_traversal_symlink_and_overlapping_roots_fail_closed(self):
        with closing(sqlite3.connect(self.source,isolation_level=None)) as c:c.execute("UPDATE users SET avatar_path='../outside.png' WHERE id=10")
        with self.assertRaises(Exception):self.run_migration()
        self.assertFalse(self.backup.exists());self.assert_empty()
        with self.assertRaises(MigrationError):migrate(source=self.source,source_uploads=self.uploads,target_url=self.pgsettings.database_url.get_secret_value(),destination_uploads=self.uploads/'nested',quiesced=True)

    def test_real_driver_failure_rolls_back_earlier_inserted_tables(self):
        def broken(connection,cursor,statement,parameters,context,many):
            if connection.dialect.name=='postgresql' and statement.startswith('INSERT INTO listing_reports'):
                raise OperationalError('Injected driver error',{},RuntimeError('Disposable test failure'))
        event.listen(Engine,'before_cursor_execute',broken)
        try:
            with self.assertRaises(OperationalError):self.run_migration()
        finally:event.remove(Engine,'before_cursor_execute',broken)
        self.assert_empty();self.assertFalse(self.destination.exists());self.assertTrue((self.backup/'source.sqlite3').exists())

    def test_real_directory_link_and_large_legitimate_stored_image(self):
        import os,random
        from io import BytesIO
        from PIL import Image
        owner=self.uploads/'avatars'/'10';original=self.root/'owned-original-avatar';owner.rename(original)
        try:
            if os.name=='nt':
                import _winapi
                _winapi.CreateJunction(str(original),str(owner))
            else:owner.symlink_to(original,target_is_directory=True)
            with self.assertRaises(Exception):self.run_migration()
            self.assertFalse(self.backup.exists());self.assertEqual((original/Path(self.avatar).name).read_bytes(),self.image)
        finally:
            if owner.is_symlink():owner.unlink()
            elif owner.exists():owner.rmdir()
            original.rename(owner)
        raw=BytesIO();Image.frombytes('RGB',(4096,4096),random.Random(57).randbytes(4096*4096*3)).save(raw,format='JPEG',quality=20)
        self.assertLess(len(raw.getvalue()),5*1024*1024)
        large=canonical_image(raw.getvalue());self.assertGreater(len(large.data),5*1024*1024)
        relative=ImageStorage(self.uploads).write(large,10)
        with closing(sqlite3.connect(self.source,isolation_level=None)) as c:c.execute('UPDATE users SET avatar_path=? WHERE id=10',(relative,))
        result=self.run_migration();self.assertEqual(result['status'],'committed-and-verified')
        self.assertEqual((self.destination/relative).read_bytes(),large.data)

    def test_destination_write_before_lock_is_not_hidden_by_stale_snapshot(self):
        inserted=[]
        def concurrent_insert(connection,cursor,statement,parameters,context,many):
            if connection.dialect.name=='postgresql' and statement.startswith('LOCK TABLE') and not inserted:
                inserted.append(True)
                with self.pg.session() as session:session.add(User(email='arrived-before-lock@sdu.edu.kz',password_hash='preserve-concurrent-record'))
        event.listen(Engine,'before_cursor_execute',concurrent_insert)
        try:
            with self.assertRaises(MigrationError):self.run_migration()
        finally:event.remove(Engine,'before_cursor_execute',concurrent_insert)
        self.assertEqual(inserted,[True]);self.assertFalse(self.backup.exists())
        with self.pg.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(User)),1)

    def test_verify_refuses_changed_sequences_without_deleting_rows_or_files(self):
        self.run_migration()
        with self.pg.engine.begin() as connection:connection.exec_driver_sql('ALTER SEQUENCE users_id_seq RESTART WITH 1')
        with self.assertRaises(MigrationError):verify_migration(backup=self.backup,target_url=self.pgsettings.database_url.get_secret_value(),destination_uploads=self.destination,quiesced=True)
        self.assertEqual((self.destination/self.photo).read_bytes(),self.image)
        with self.pg.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(User)),5)

    def test_new_source_sidecar_before_commit_aborts_and_preserves_it(self):
        sidecar=Path(str(self.source)+'-wal')
        def interrupted_quiescence(stage):
            if stage=='published':sidecar.write_bytes(b'Unexpected writer sidecar; preserve for recovery')
        with self.assertRaises(MigrationError):self.run_migration(_fault=interrupted_quiescence)
        self.assert_empty();self.assertFalse(self.destination.exists())
        self.assertEqual(digest_bytes(self.source),self.before)
        self.assertEqual(sidecar.read_bytes(),b'Unexpected writer sidecar; preserve for recovery')
        self.assertTrue((self.backup/'source.sqlite3').exists())
        self.assertEqual(json.loads((self.backup/'recovery.json').read_text())['state'],'rolled-back-owned-files-cleaned')
