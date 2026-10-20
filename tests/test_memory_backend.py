"""Real volatile API/storage: loopback SMTP, no PostgreSQL or frontend mock."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
import re
import threading
import unittest
from unittest.mock import Mock, patch
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from backend.admin import main as provision
from backend.app import create_app
from backend.authentication import AuthenticationError, authenticate_student
from backend.config import ConfigurationError, load_settings
from backend.database import Database
from backend.email_codes import utc_now
from backend.mail import SmtpSender
from backend.models import Category, EmailCode, Listing, ListingPhoto, ListingReport, RefreshSession, User
from backend.sessions import csrf_token, new_login_session, rotate_refresh_session
from backend.verification import verify_registration_code
from smtp_support import ExplicitTestSMTP, loopback_smtp
from test_avatar_integration import picture
from contract_support import assert_response

PASSWORD = "MEMORY_TEST_ONLY_PASSWORD_123"
NEW_PASSWORD = "MEMORY_NEW_TEST_PASSWORD_456"


def memory_settings(**overrides):
    return load_settings(environ={"APP_ENV":"test", "DATABASE_URL":"sqlite+pysqlite:///:memory:",
        "JWT_SECRET_KEY":"MEMORY_TEST_ONLY_"+"x"*48, **overrides}, env_file=None)


class MemoryBackendTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.smtp = self.stack.enter_context(loopback_smtp())
        self.settings = memory_settings(SMTP_HOST="127.0.0.1",SMTP_PORT=str(self.smtp.server_address[1]),
            SMTP_USERNAME="SYNTHETIC_TEST_USER", SMTP_PASSWORD="SYNTHETIC_TEST_PASSWORD",
            SMTP_FROM_EMAIL="verification@example.invalid")
        self.app = create_app(self.settings, sender=SmtpSender(self.settings, smtp_factory=ExplicitTestSMTP))
        self.client = self.stack.enter_context(TestClient(self.app))
        self.database = self.app.state.database
        self.settings = self.app.state.settings

    def request(self, method, path, status, **kwargs):
        response = self.client.request(method,path,**kwargs)
        self.assertEqual(response.status_code,status,response.text)
        return response

    def register(self, name):
        email = name+"@sdu.edu.kz"
        response = self.request("POST","/auth/register",201,json={"email":email,"password":PASSWORD})
        message = next(message for sender,recipient,message in reversed(self.smtp.messages) if recipient==email)
        code = re.search(r"code is: (\d{6})",message.get_content()).group(1)
        self.assertNotIn(code,response.text)
        return response.json()["id"],email,code

    def account(self,name):
        id,email,code = self.register(name)
        self.request("POST","/auth/verify-email",200,json={"email":email,"code":code})
        result=self.request("POST","/auth/login",200,json={"email":email,"password":PASSWORD})
        return id,email,{"Authorization":"Bearer "+result.json()["access_token"]}

    def listing(self,headers):
        self.request("PATCH","/users/me",200,headers=headers,json={"name":"Memory seller","phone":"+77001234567"})
        return self.request("POST","/listings",201,headers=headers,json={"title":"Memory sample book ТЕСТ",
            "description":"A real API disposable memory item.","price":"12.34","category_id":3,"condition":"used"}).json()["id"]

    def photo(self,id,headers,status=201):
        return self.request("POST",f"/listings/{id}/photos",status,headers=headers,
            files={"image":("sample.png",picture(),"image/png")})

    def admin(self,name="admin"):
        id,email,headers=self.account(name)
        with redirect_stdout(StringIO()):
            self.assertEqual(provision(["--email",email],database=self.database),0)
        self.request("GET","/admin/me",200,headers=headers)
        return id,email,headers

    def test_real_smtp_to_private_images_publication_reports_and_cascade_deletion(self):
        owner,email,headers=self.account("owner")
        buyer,buyer_email,buyer_headers=self.account("buyer")
        admin,admin_email,admin_headers=self.admin()
        id=self.listing(headers)
        self.request("POST","/users/me/avatar",200,headers=headers,files={"image":("avatar.png",picture(),"image/png")})
        self.assertTrue(self.request("GET","/users/me/avatar",200,headers=headers).content.startswith(bytes([137,80,78,71])))
        photo=self.photo(id,headers).json()
        self.request("GET",photo["url"],404,headers=buyer_headers)
        self.assertEqual(self.request("GET","/listings",200,headers=buyer_headers).json()["total"],0)
        self.request("POST",f"/admin/listings/{id}/approve",200,headers=admin_headers)
        feed=self.request("GET","/listings?q=sample&min_price=12.34&max_price=12.34",200,headers=buyer_headers)
        self.assertEqual(feed.json()["total"],1)
        self.assertEqual(self.request("GET","/listings?q=тест",200,headers=buyer_headers).json()["total"],1)
        detail=self.request("GET",f"/listings/{id}",200,headers=buyer_headers)
        self.assertIn("+77001234567",detail.text)
        self.assertNotIn(email,detail.text)
        binary=self.request("GET",photo["url"],200,headers=buyer_headers)
        assert_response(self,self.app.openapi(),"/listings/{listing_id}/photos/{photo_id}","get",binary,200)
        self.request("POST",f"/listings/{id}/reports",202,headers=buyer_headers,json={"reason":"spam"})
        reports=self.request("GET","/admin/reports",200,headers=admin_headers).json()["items"]
        report_id=reports[0]["id"]
        self.request("POST",f"/admin/reports/{report_id}/review",200,headers=admin_headers)
        self.request("POST",f"/admin/listings/{id}/remove",200,headers=admin_headers)
        self.request("GET",f"/listings/{id}",404,headers=buyer_headers)
        self.request("DELETE",f"/listings/{id}",200,headers=headers)
        with self.database.session() as session:
            self.assertIsNone(session.get(Listing,id))
            self.assertEqual(session.scalar(select(func.count()).select_from(ListingPhoto)),0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ListingReport)),0)
        # Account deletion also cascades its remaining listing/photo, code and session.
        second=self.listing(headers);self.photo(second,headers)
        self.request("DELETE","/users/me",200,headers=headers,json={"current_password":PASSWORD})
        self.request("GET","/auth/me",401,headers=headers)
        with self.database.session() as session:
            self.assertIsNone(session.get(User,owner))
            for model in [Listing,ListingPhoto,EmailCode,RefreshSession]:
                column=model.owner_id if model is Listing else model.user_id if model in [EmailCode,RefreshSession] else model.listing_id
                value=second if model is ListingPhoto else owner
                self.assertEqual(session.scalar(select(func.count()).select_from(model).where(column==value)),0)
            self.assertIsNotNone(session.get(User,buyer))
        self.assertEqual(list(self.settings.upload_dir.rglob("*.png")),[])

    def test_empty_isolated_apps_owned_uploads_shutdown_restart_and_production_rejection(self):
        configured=self.settings.upload_dir
        with TestClient(create_app(self.settings)) as other:
            root=other.app.state.settings.upload_dir
            self.assertNotEqual(root,configured)
            self.assertTrue(root.exists())
            with other.app.state.database.session() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(User)),0)
                self.assertEqual(session.scalar(select(func.count()).select_from(Category)),5)
            (root/"owned-test-marker").write_text("temporary",encoding="utf-8")
        self.assertFalse(root.exists())
        self.assertTrue(configured.exists())
        with self.assertRaises(RuntimeError):
            with other.app.state.database.session():pass
        self.account("isolated")
        with TestClient(create_app(memory_settings())) as fresh:
            with fresh.app.state.database.session() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(User)),0)
        with self.assertRaises(ConfigurationError):
            memory_settings(APP_ENV="production",FRONTEND_ORIGINS='["https://example.invalid"]')
        # Even a caller bypassing Settings validation cannot enable production memory.
        with self.assertRaises(ValueError):Database(self.settings.model_copy(update={"app_env":"production"}))

    def test_missing_and_failed_mail_roll_back_without_seed_or_bypass(self):
        with TestClient(create_app(memory_settings())) as client:
            result=client.post("/auth/register",json={"email":"unconfigured@sdu.edu.kz","password":PASSWORD})
            self.assertEqual(result.status_code,503)
            with client.app.state.database.session() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(User)),0)
                self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)),0)
        id,email,code=self.register("duplicate")
        self.request("POST","/auth/register",409,json={"email":email,"password":PASSWORD})
        self.assertEqual(len(self.smtp.messages),1)
        with redirect_stdout(StringIO()):self.assertEqual(provision(["--email",email],database=self.database),1)

    def test_concurrent_wrong_attempts_and_one_time_consumption(self):
        id,email,code=self.register("attempts")
        wrong="000001" if code!="000001" else "000002"
        barrier=threading.Barrier(8)
        def attempt(_):
            barrier.wait()
            return self.client.post("/auth/verify-email",json={"email":email,"code":wrong}).status_code
        with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(list(pool.map(attempt,range(8))),[400]*8)
        with self.database.session() as session:
            record=session.scalar(select(EmailCode).where(EmailCode.user_id==id))
            self.assertEqual(record.wrong_attempts,5);self.assertIsNotNone(record.invalidated_at)
            self.assertFalse(session.get(User,id).verified)
        id,email,code=self.register("once")
        barrier=threading.Barrier(4)
        def verify(_):
            barrier.wait()
            return self.client.post("/auth/verify-email",json={"email":email,"code":code}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sorted(pool.map(verify,range(4))),[200,400,400,400])
        with self.database.session() as session:
            self.assertTrue(session.get(User,id).verified)
            self.assertIsNotNone(session.scalar(select(EmailCode).where(EmailCode.user_id==id)).consumed_at)

    def test_waiting_verification_reads_fresh_time_after_guard(self):
        id,email,code=self.register("expires")
        entered=threading.Event();observed=threading.Event()
        with self.database.session() as session:
            record=session.scalar(select(EmailCode).where(EmailCode.user_id==id));expires=record.expires_at
            def clock():observed.set();return expires
            def waiting():
                entered.set()
                return verify_registration_code(self.database,email,code,self.settings,clock=clock)
            pool=ThreadPoolExecutor(max_workers=1)
            future=pool.submit(waiting);self.assertTrue(entered.wait(3));self.assertFalse(observed.wait(.05))
        try:self.assertFalse(future.result(timeout=5))
        finally:pool.shutdown()
        self.assertTrue(observed.is_set())
        with self.database.session() as session:self.assertFalse(session.get(User,id).verified)

    def test_real_http_refresh_and_concurrent_replay_revoke_family(self):
        id,email,headers=self.account("rotate")
        origin=self.settings.frontend_origins[0]
        raw=self.client.cookies.get("refresh_token")
        csrf=self.request("GET","/auth/csrf",200,headers={"Origin":origin}).json()["csrf_token"]
        self.request("POST","/auth/refresh",403,headers={"Origin":origin})
        barrier=threading.Barrier(2)
        def rotate(_):
            barrier.wait()
            return rotate_refresh_session(self.database,raw,csrf,self.settings,clock=utc_now)
        with ThreadPoolExecutor(max_workers=2) as pool:grants=list(pool.map(rotate,range(2)))
        self.assertEqual(sum(grant is not None for grant in grants),1)
        self.request("GET","/auth/me",401,headers=headers)
        with self.database.session() as session:
            rows=list(session.scalars(select(RefreshSession).where(RefreshSession.user_id==id)))
            self.assertEqual(len(rows),2);self.assertTrue(all(row.revoked_at is not None for row in rows))
            first=next(row for row in rows if row.predecessor_id is None)
            second=next(row for row in rows if row.predecessor_id is not None)
            self.assertEqual(first.successor_id,second.id);self.assertEqual(second.predecessor_id,first.id)
            self.assertEqual(first.expires_at,second.expires_at)
        # Independent fresh family exercises the real HTTP refresh response contract.
        login=self.request("POST","/auth/login",200,json={"email":email,"password":PASSWORD})
        old=self.client.cookies.get("refresh_token")
        csrf=self.request("GET","/auth/csrf",200,headers={"Origin":origin}).json()["csrf_token"]
        refresh=self.request("POST","/auth/refresh",200,headers={"Origin":origin,"X-CSRF-Token":csrf})
        assert_response(self,self.app.openapi(),"/auth/refresh","post",refresh,200)
        self.client.cookies.set("refresh_token",old,domain="testserver.local",path="/auth")
        self.request("POST","/auth/refresh",401,headers={"Origin":origin,"X-CSRF-Token":csrf})
        self.request("GET","/auth/me",401,headers={"Authorization":"Bearer "+refresh.json()["access_token"]})

    def test_concurrent_upload_slots_and_failed_commit_cleanup(self):
        id,email,headers=self.account("photos");listing=self.listing(headers)
        for _ in range(4):self.photo(listing,headers)
        barrier=threading.Barrier(3)
        def upload(_):
            barrier.wait()
            return self.client.post(f"/listings/{listing}/photos",headers=headers,files={"image":("sample.png",picture(),"image/png")}).status_code
        with ThreadPoolExecutor(max_workers=3) as pool:statuses=list(pool.map(upload,range(3)))
        self.assertEqual(statuses.count(201),1);self.assertEqual(statuses.count(409),2)
        with self.database.session() as session:
            positions=list(session.scalars(select(ListingPhoto.position).where(ListingPhoto.listing_id==listing).order_by(ListingPhoto.position)))
            self.assertEqual(positions,[1,2,3,4,5])
        from backend.listing_photos import append_listing_photo
        from sqlalchemy.orm import Session
        second=self.listing(headers)
        before=set(self.settings.upload_dir.rglob("*.png"))
        with patch.object(Session,"commit",side_effect=RuntimeError("synthetic failed commit")):
            with self.assertRaises(RuntimeError):append_listing_photo(self.database,id,headers["Authorization"].split()[1],second,picture(),self.settings,clock=utc_now)
        self.assertEqual(set(self.settings.upload_dir.rglob("*.png")),before)
        with self.database.session() as session:self.assertEqual(session.scalar(select(func.count()).select_from(ListingPhoto).where(ListingPhoto.listing_id==second)),0)

    def test_conflicting_publication_and_credential_session_changes(self):
        owner,email,headers=self.account("seller");id=self.listing(headers)
        admin,admin_email,admin_headers=self.admin()
        barrier=threading.Barrier(2)
        def decide(action):
            barrier.wait()
            return self.client.post(f"/admin/listings/{id}/{action}",headers=admin_headers,
                **({"json":{"reason":"Review failed"}} if action=="reject" else {})).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(decide,["approve","reject"])),[200,409])
        with self.database.session() as session:
            item=session.get(Listing,id)
            self.assertIn(item.status,["active","rejected"])
            self.assertEqual(item.published_at is not None,item.status=="active")
        # Previously authenticated credential cannot create a new family after password change.
        authenticated=authenticate_student(self.database,email,PASSWORD)
        token=headers["Authorization"].split()[1]
        entered=threading.Event();release=threading.Event();login_started=threading.Event()
        from argon2 import PasswordHasher
        real_hasher=PasswordHasher()
        delayed_hasher=Mock(wraps=real_hasher)
        def hash_after_wait(password):
            entered.set()
            if not release.wait(5):raise AssertionError("Password-change release timed out")
            return real_hasher.hash(password)
        delayed_hasher.hash.side_effect=hash_after_wait
        def stale_login():
            login_started.set()
            return new_login_session(self.database,owner,self.settings,clock=utc_now,verified_password_hash=authenticated.password_hash)
        with patch("backend.passwords.PasswordHasher",return_value=delayed_hasher):
            with ThreadPoolExecutor(max_workers=2) as pool:
                change=pool.submit(self.client.post,"/auth/change-password",headers=headers,
                    json={"current_password":PASSWORD,"new_password":NEW_PASSWORD})
                try:
                    self.assertTrue(entered.wait(5))
                    future=pool.submit(stale_login);self.assertTrue(login_started.wait(3))
                finally:release.set()
                self.assertEqual(change.result(timeout=10).status_code,204)
                with self.assertRaises(AuthenticationError):future.result(timeout=5)
        self.request("GET","/auth/me",401,headers=headers)
        self.request("POST","/auth/login",401,json={"email":email,"password":PASSWORD})
        self.request("POST","/auth/login",200,json={"email":email,"password":NEW_PASSWORD})

    def test_concurrent_approval_and_suspension_recheck_visibility_and_sessions(self):
        owner,email,headers=self.account("suspendowner");id=self.listing(headers)
        photo=self.photo(id,headers).json()
        admin,admin_email,admin_headers=self.admin()
        barrier=threading.Barrier(2)
        def mutation(action):
            barrier.wait()
            if action=="approve":
                return self.client.post(f"/admin/listings/{id}/approve",headers=admin_headers).status_code
            return self.client.patch(f"/admin/users/{owner}/suspension",headers=admin_headers,json={"suspended":True}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(mutation,["approve","suspend"]))
        self.assertIn(results[0],[200,409]);self.assertEqual(results[1],200)
        self.request("GET","/auth/me",401,headers=headers)
        self.assertEqual(self.request("GET","/listings",200,headers=admin_headers).json()["total"],0)
        self.request("GET",f"/listings/{id}",404,headers=admin_headers)
        self.request("GET",photo["url"],404,headers=admin_headers)
        with self.database.session() as session:
            self.assertTrue(session.get(User,owner).suspended)
            self.assertTrue(all(row.revoked_at is not None for row in session.scalars(select(RefreshSession).where(RefreshSession.user_id==owner))))
            item=session.get(Listing,id)
            self.assertIn(item.status,["pending","active"])
            self.assertEqual(item.published_at is not None,item.status=="active")

    def test_orm_constraints_exact_money_utc_uuid_and_rollback(self):
        id,email,headers=self.account("integrity");listing_id=self.listing(headers)
        def rejected(sql,params=None):
            with self.assertRaises(IntegrityError):
                with self.database.session() as session:session.execute(text(sql),params or {})
        rejected("UPDATE users SET email='UPPER@sdu.edu.kz' WHERE id=:id",{"id":id})
        rejected("UPDATE users SET email='bad @sdu.edu.kz' WHERE id=:id",{"id":id})
        rejected("UPDATE users SET role='root' WHERE id=:id",{"id":id})
        rejected("UPDATE users SET verified=2 WHERE id=:id",{"id":id})
        rejected("UPDATE email_codes SET wrong_attempts=6 WHERE user_id=:id",{"id":id})
        rejected("UPDATE email_codes SET expires_at=created_at WHERE user_id=:id",{"id":id})
        rejected("UPDATE listings SET owner_id=999999 WHERE id=:id",{"id":listing_id})
        rejected("UPDATE listings SET status='active' WHERE id=:id",{"id":listing_id})
        rejected("UPDATE listings SET status='rejected',rejection_reason=' ' WHERE id=:id",{"id":listing_id})
        rejected("UPDATE listings SET price=12.345 WHERE id=:id",{"id":listing_id})
        rejected("UPDATE categories SET name='Incorrect' WHERE id=1")
        rejected("UPDATE refresh_sessions SET successor_id=id WHERE user_id=:id",{"id":id})
        rejected("UPDATE refresh_sessions SET successor_id='ffffffffffffffffffffffffffffffff' WHERE user_id=:id",{"id":id})
        rejected("UPDATE users SET email=:email WHERE id=:id",{"id":id,"email":"x"*255+"@sdu.edu.kz"})
        # SQLite's registered UUID default also works for direct SQL insertion.
        with self.database.session() as session:
            session.execute(text("INSERT INTO refresh_sessions(user_id,token_digest,expires_at) VALUES (:id,'direct-sql-digest',:expires)"),
                {"id":id,"expires":(utc_now()+timedelta(days=1)).replace(tzinfo=None)})
        with self.database.session() as session:
            direct=session.scalar(select(RefreshSession).where(RefreshSession.token_digest=="direct-sql-digest"))
            self.assertIsInstance(direct.id,uuid.UUID);self.assertIsInstance(direct.family_id,uuid.UUID)
        for price in [Decimal("-0.01"),Decimal("1000000000.01"),Decimal("12.345"),Decimal("NaN"),1.1]:
            with self.subTest(price=price),self.assertRaises(StatementError):
                with self.database.session() as session:session.get(Listing,listing_id).price=price
        for price in [Decimal("0.00"),Decimal("1000000000.00"),Decimal("0.01"),Decimal("12.3400")]:
            with self.database.session() as session:session.get(Listing,listing_id).price=price
            with self.database.session() as session:self.assertEqual(session.get(Listing,listing_id).price,price)
        offset=timezone(timedelta(hours=6));aware=datetime.now(offset)
        with self.database.session() as session:session.get(User,id).created_at=aware
        with self.database.session() as session:
            self.assertEqual(session.get(User,id).created_at,aware)
            self.assertEqual(session.get(User,id).created_at.tzinfo,timezone.utc)
            code=session.scalar(select(EmailCode).where(EmailCode.user_id==id))
            self.assertEqual(code.expires_at-code.created_at,timedelta(minutes=10))
            self.assertIsInstance(session.scalar(select(RefreshSession.id)),uuid.UUID)
        with self.assertRaises(StatementError):
            with self.database.session() as session:session.get(User,id).created_at=datetime.now()
        self.photo(listing_id,headers)
        rejected("INSERT INTO listing_photos(listing_id,storage_path,position) VALUES (:id,:path,1)",{"id":listing_id,"path":f"listings/{listing_id}/"+"a"*32+".png"})
        rejected("INSERT INTO listing_photos(listing_id,storage_path,position) VALUES (:id,:path,6)",{"id":listing_id,"path":f"listings/{listing_id}/"+"b"*32+".png"})
        rejected("INSERT INTO listing_photos(listing_id,storage_path,position) VALUES (:id,'../escape.png',2)",{"id":listing_id})
        with self.assertRaises(RuntimeError):
            with self.database.session() as session:
                session.get(User,id).name="Must roll back";session.flush();raise RuntimeError("rollback")
        with self.database.session() as session:
            self.assertEqual(session.get(User,id).name,"Memory seller")
            self.assertEqual(session.get(Listing,listing_id).status,"pending")
            self.assertEqual(session.get(Listing,listing_id).price,Decimal("12.34"))
