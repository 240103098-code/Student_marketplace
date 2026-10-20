"""Actual file SQLite migrations, persistent HTTP and independent writers."""
from contextlib import ExitStack, closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import sqlite3
import jwt
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from backend.app import create_app
from backend.config import ConfigurationError, REPOSITORY_ROOT, load_settings
from backend.database import Base, Database
from backend.mail import SmtpSender
from backend.models import Category, EmailCode, Listing, ListingPhoto, ListingReport, RefreshSession, User
from backend.sessions import csrf_token
from smtp_support import ExplicitTestSMTP, loopback_smtp
import test_memory_backend as memory


class PersistentSQLiteTest(memory.MemoryBackendTest):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.directory=Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="student-marketplace-sqlite-test-")))
        self.file=self.directory/"data with spaces"/"marketplace.sqlite3"
        self.smtp=self.stack.enter_context(loopback_smtp())
        self.settings=memory.memory_settings(DATABASE_URL="sqlite+pysqlite:///"+str(self.file),UPLOAD_DIR=str(self.directory/"uploads"),
            SMTP_HOST="127.0.0.1",SMTP_PORT=str(self.smtp.server_address[1]),SMTP_USERNAME="SYNTHETIC_TEST_USER",
            SMTP_PASSWORD="SYNTHETIC_TEST_PASSWORD",SMTP_FROM_EMAIL="verification@example.invalid")
        self.configuration=Config(str(REPOSITORY_ROOT/"alembic-sqlite.ini"))
        self.configuration.attributes["settings"]=self.settings
        # Persistent startup must never silently substitute metadata.create_all.
        with patch.object(Base.metadata,"create_all",side_effect=AssertionError("Persistent storage requires migrations")):
            command.upgrade(self.configuration,"head")
            self.app=create_app(self.settings,sender=SmtpSender(self.settings,smtp_factory=ExplicitTestSMTP))
        self.database=self.app.state.database
        self.stack.callback(self.database.dispose)
        self.client=self.stack.enter_context(TestClient(self.app))

    def child_environment(self,**values):
        return dict(os.environ,APP_ENV="test",DATABASE_URL=self.settings.database_url.get_secret_value(),
            JWT_SECRET_KEY=self.settings.jwt_secret_key.get_secret_value(),UPLOAD_DIR=str(self.settings.upload_dir),**values)

    def test_empty_isolated_apps_owned_uploads_shutdown_restart_and_production_rejection(self):
        # Override memory-specific lifetime assertion: FILE state/images survive.
        owner,email,headers=self.account("persistowner")
        buyer,buyer_email,buyer_headers=self.account("persistbuyer")
        admin,admin_email,admin_headers=self.account("persistadmin")
        promoted=subprocess.run([sys.executable,"-m","backend.admin","--email",admin_email],
            env=self.child_environment(),cwd=REPOSITORY_ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(promoted.returncode,0,promoted.stderr)
        self.assertEqual(promoted.stdout,"Admin provisioning completed.\n")
        id=self.listing(headers);photo=self.photo(id,headers).json()
        self.request("POST",f"/admin/listings/{id}/approve",200,headers=admin_headers)
        self.request("POST",f"/listings/{id}/reports",202,headers=buyer_headers,json={"reason":"spam"})
        report=self.request("GET","/admin/reports",200,headers=admin_headers).json()["items"][0]
        self.request("POST",f"/admin/reports/{report['id']}/review",200,headers=admin_headers)
        before_files=set(self.settings.upload_dir.rglob("*.png"));self.assertEqual(len(before_files),1)
        self.client.__exit__(None,None,None)
        self.assertTrue(self.settings.upload_dir.exists());self.assertEqual(set(self.settings.upload_dir.rglob("*.png")),before_files)
        self.assertTrue(self.database.check_connection()) # file dispose/reopen is supported
        self.database.dispose()
        with TestClient(create_app(self.settings)) as reopened:
            self.assertEqual(reopened.get("/auth/me",headers=headers).status_code,200)
            self.assertEqual(reopened.get("/admin/me",headers=admin_headers).status_code,200)
            item=reopened.get(f"/listings/{id}",headers=buyer_headers)
            self.assertEqual(item.status_code,200,item.text);self.assertEqual(item.json()["price"],"12.34")
            self.assertEqual(reopened.get(photo["url"],headers=buyer_headers).status_code,200)
            self.assertIsNotNone(reopened.get("/admin/reports?state=reviewed",headers=admin_headers).json()["items"][0]["reviewed_at"])
        script="""
import json
from sqlalchemy import func,select
from backend.config import load_settings
from backend.database import Database
from backend.models import User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport
with_db=Database(load_settings(env_file=None))
with with_db.session() as session:
 result={m.__tablename__:session.scalar(select(func.count()).select_from(m)) for m in [User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport]}
 assert session.scalar(select(Listing.price)) == __import__('decimal').Decimal('12.34')
 assert session.scalar(select(EmailCode.expires_at)).tzinfo is not None
 assert session.scalar(select(ListingReport.reviewed_at)) is not None
 print(json.dumps(result))
with_db.dispose()
"""
        result=subprocess.run([sys.executable,"-c",script],env=self.child_environment(),cwd=REPOSITORY_ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{"users":3,"email_codes":3,"refresh_sessions":3,"listings":1,"listing_photos":1,"listing_reports":1})
        # Migration/check commands are non-resetting and preserve files and rows.
        command.upgrade(self.configuration,"head")
        with self.database.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(User)),3)
        self.assertEqual(set(self.settings.upload_dir.rglob("*.png")),before_files)

    def test_missing_and_failed_mail_roll_back_without_seed_or_bypass(self):
        missing=self.settings.model_copy(update={"smtp_host":None,"smtp_port":None,"smtp_username":None,"smtp_password":None,"smtp_from_email":None})
        with TestClient(create_app(missing)) as client:
            response=client.post("/auth/register",json={"email":"missing@sdu.edu.kz","password":memory.PASSWORD})
            self.assertEqual(response.status_code,503)
        with self.database.session() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(User)),0)
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)),0)
        self.assertFalse(self.database.is_memory)
        self.register("duplicate")
        self.request("POST","/auth/register",409,json={"email":"duplicate@sdu.edu.kz","password":memory.PASSWORD})
        self.assertEqual(len(self.smtp.messages),1)

    def test_sqlite_migration_roundtrip_and_wal_foreignkeys_no_pg_stream(self):
        with self.database.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(),1)
            self.assertEqual(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one(),"wal")
            self.assertEqual(connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(),1500)
            self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version_sqlite")).scalar_one(),"sqlite_0001")
            self.assertNotIn("alembic_version",inspect(connection).get_table_names())
        output=StringIO();self.configuration.stdout=output
        command.current(self.configuration);self.assertIn("sqlite_0001",output.getvalue())
        command.upgrade(self.configuration,"head")
        with self.database.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(Category)),5)
        # Only this fixture-created disposable file is downgraded.
        self.assertTrue(self.file.is_relative_to(self.directory))
        self.database.dispose();command.downgrade(self.configuration,"base")
        with self.database.engine.connect() as connection:self.assertEqual(inspect(connection).get_table_names(),["alembic_version_sqlite"])
        command.upgrade(self.configuration,"head")
        with self.database.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(Category)),5)
        # An unrelated existing file/schema is never overwritten or stamped.
        existing=self.directory/"existing.sqlite3"
        with closing(sqlite3.connect(existing)) as connection:
            connection.execute("CREATE TABLE users(marker TEXT)")
            connection.execute("INSERT INTO users VALUES ('preserve-existing')")
            connection.commit()
        other=Config(str(REPOSITORY_ROOT/"alembic-sqlite.ini"))
        other.attributes["settings"]=memory.memory_settings(DATABASE_URL="sqlite+pysqlite:///"+str(existing))
        with self.assertRaisesRegex(RuntimeError,"SQLite migration failed"):command.upgrade(other,"head")
        with closing(sqlite3.connect(existing)) as connection:
            self.assertEqual(connection.execute("SELECT marker FROM users").fetchone()[0],"preserve-existing")
            self.assertFalse(connection.execute("SELECT name FROM sqlite_master WHERE name='categories'").fetchall())
        pg=Config(str(REPOSITORY_ROOT/"alembic.ini"));pg.attributes["settings"]=self.settings
        with self.assertRaisesRegex(RuntimeError,"PostgreSQL migration stream"):command.upgrade(pg,"head")

    def test_busy_exhaustion_is_bounded_safe_503_without_replay_or_partial_mutation(self):
        id,email,headers=self.account("busy")
        with TestClient(create_app(self.settings)) as competitor:
            with self.database.session() as session:
                session.get(User,id).name="Writer committed"
                started=time.monotonic()
                response=competitor.patch("/users/me",headers=headers,json={"name":"Must never replay"})
                duration=time.monotonic()-started
                self.assertEqual(response.status_code,503,response.text)
                self.assertEqual(response.headers["retry-after"],"1")
                self.assertGreater(duration,1);self.assertLess(duration,4)
                self.assertNotIn(str(self.file),response.text)
                self.assertNotIn("locked",response.text)
                self.assertIn("no-store",response.headers["cache-control"])
            with self.database.session() as session:self.assertEqual(session.get(User,id).name,"Writer committed")
            self.assertEqual(competitor.get("/users/me",headers=headers).json()["name"],"Writer committed")
            # Waiting auth guards validate JWT expiry after BEGIN IMMEDIATE,
            # not before an independent writer releases its reservation.
            expires=jwt.decode(headers["Authorization"].split()[1],options={"verify_signature":False})["exp"]
            now=[datetime.now(timezone.utc)]
            competitor.app.state.clock=lambda:now[0]
            beginning=threading.Event()
            @event.listens_for(competitor.app.state.database.engine,"before_cursor_execute")
            def about_to_wait(connection,cursor,statement,parameters,context,executemany):
                if statement=="BEGIN IMMEDIATE":beginning.set()
            pool=ThreadPoolExecutor(max_workers=1)
            try:
                with self.database.session():
                    future=pool.submit(competitor.get,"/auth/me",headers=headers)
                    self.assertTrue(beginning.wait(3))
                    now[0]=datetime.fromtimestamp(expires,timezone.utc)
                self.assertEqual(future.result(timeout=4).status_code,401)
            finally:pool.shutdown()


    def run_competing_processes(self,operation,**values):
        script="""
import os
from backend.config import load_settings
from backend.database import Database
from backend.email_codes import utc_now
from backend.verification import verify_registration_code
from backend.sessions import rotate_refresh_session
settings=load_settings(env_file=None);db=Database(settings)
print('ready',flush=True);input()
if os.environ['CHILD_OPERATION']=='verify':
 result=verify_registration_code(db,os.environ['CHILD_EMAIL'],os.environ['CHILD_CODE'],settings)
elif os.environ['CHILD_OPERATION']=='attempts':
 result=[verify_registration_code(db,os.environ['CHILD_EMAIL'],os.environ['CHILD_CODE'],settings) for _ in range(4)]
 result=any(result)
else:
 result=rotate_refresh_session(db,os.environ['CHILD_REFRESH'],os.environ['CHILD_CSRF'],settings,clock=utc_now) is not None
print(int(bool(result)),flush=True);db.dispose()
"""
        processes=[]
        try:
            for _ in range(2):
                process=subprocess.Popen([sys.executable,"-c",script],env=self.child_environment(CHILD_OPERATION=operation,**values),
                    cwd=REPOSITORY_ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                processes.append(process)
            for process in processes:self.assertEqual(process.stdout.readline().strip(),"ready")
            for process in processes:process.stdin.write("go\n");process.stdin.flush()
            result=[]
            for process in processes:
                out,error=process.communicate(timeout=10)
                self.assertEqual(process.returncode,0,error);result.append(int(out.strip()))
            return sorted(result)
        finally:
            for process in processes:
                if process.poll() is None:process.kill();process.wait(timeout=5)

    def test_independent_processes_code_attempts_consume_and_refresh_replay_survive_restart(self):
        id,email,code=self.register("processattempt")
        wrong="000001" if code!="000001" else "000002"
        self.assertEqual(self.run_competing_processes("attempts",CHILD_EMAIL=email,CHILD_CODE=wrong),[0,0])
        with self.database.session() as session:
            record=session.scalar(select(EmailCode).where(EmailCode.user_id==id));self.assertEqual(record.wrong_attempts,5);self.assertIsNotNone(record.invalidated_at)
        id,email,code=self.register("processonce")
        self.assertEqual(self.run_competing_processes("verify",CHILD_EMAIL=email,CHILD_CODE=code),[0,1])
        self.request("POST","/auth/login",200,json={"email":email,"password":memory.PASSWORD})
        raw=self.client.cookies.get("refresh_token")
        csrf=self.request("GET","/auth/csrf",200,headers={"Origin":self.settings.frontend_origins[0]}).json()["csrf_token"]
        self.assertEqual(self.run_competing_processes("refresh",CHILD_REFRESH=raw,CHILD_CSRF=csrf),[0,1])
        self.database.dispose()
        reopened=Database(self.settings);self.stack.callback(reopened.dispose)
        with reopened.session() as session:
            rows=list(session.scalars(select(RefreshSession).where(RefreshSession.user_id==id)))
            self.assertEqual(len(rows),2);self.assertTrue(all(row.revoked_at is not None for row in rows))


class PersistentConfigurationTest(unittest.TestCase):
    def test_default_and_relative_paths_do_not_depend_on_cwd(self):
        existed=(REPOSITORY_ROOT/"backend/data/marketplace.sqlite3").exists()
        settings=load_settings(environ={"JWT_SECRET_KEY":"TEST_ONLY_"+"x"*48},env_file=None)
        self.assertEqual(Path(Database(settings).engine.url.database),REPOSITORY_ROOT/"backend/data/marketplace.sqlite3")
        self.assertEqual((REPOSITORY_ROOT/"backend/data/marketplace.sqlite3").exists(),existed)
        with tempfile.TemporaryDirectory() as directory:
            previous=Path.cwd()
            try:
                os.chdir(directory)
                relative=memory.memory_settings(DATABASE_URL="sqlite+pysqlite:///backend/data/custom.sqlite3")
                self.assertEqual(Path(Database(relative).engine.url.database),REPOSITORY_ROOT/"backend/data/custom.sqlite3")
            finally:os.chdir(previous)
        with self.assertRaises(ConfigurationError):load_settings(environ={},env_file=None)
        with self.assertRaises(ConfigurationError):load_settings(environ={"APP_ENV":"production","JWT_SECRET_KEY":"TEST_ONLY_"+"x"*48,"FRONTEND_ORIGINS":'["https://example.invalid"]'},env_file=None)

    def test_strict_local_url_forms_and_windows_absolute_path(self):
        for url in ["sqlite+pysqlite://remote/file.db","sqlite+pysqlite:///file:unsafe?mode=memory","sqlite+pysqlite:///file.db?x=1", "sqlite+pysqlite:///file.db#fragment", "sqlite+pysqlite://///remote/share/file.db", "sqlite+pysqlite:///C:relative.db", "sqlite:///:memory:", "sqlite+pysqlite://"]:
            with self.subTest(url=url),self.assertRaises(ConfigurationError):memory.memory_settings(DATABASE_URL=url)
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"windows path.sqlite3"
            settings=memory.memory_settings(DATABASE_URL="sqlite+pysqlite:///"+target.as_posix())
            self.assertEqual(Path(Database(settings).engine.url.database),target)
