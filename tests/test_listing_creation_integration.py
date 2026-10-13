from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from threading import Event
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.listings import create_own_listing
from backend.models import CATEGORIES, Listing, User
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database

VALID={'title':'Useful book','description':'A useful textbook.','price':'12.34','category_id':1,'condition':'used'}
FIELDS={'id','title','description','price','currency','category_id','condition','status','created_at','published_at'}


class ListingCreationPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings,cls.database,_=open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.configuration.attributes['settings']=cls.settings
        command.upgrade(cls.configuration,'head');cls.addClassCleanup(command.downgrade,cls.configuration,'0001_baseline')

    def setUp(self):
        self.now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        self.context=TestClient(create_app(self.settings,self.database,clock=lambda:self.now));self.client=self.context.__enter__()
        with self.database.session() as session:
            self.user=User(email='seller@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_LISTING_PASSWORD_123'),verified=True,phone='+77001234567')
            self.other=User(email='other@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_LISTING_PASSWORD_123'),verified=True)
            session.add_all([self.user,self.other]);session.flush()
        self.headers={'Authorization':'Bearer '+self.login()}

    def tearDown(self):
        self.context.__exit__(None,None,None)
        with self.database.session() as session:session.execute(delete(User))

    def login(self):
        result=self.client.post('/auth/login',json={'email':self.user.email,'password':'TEST_LISTING_PASSWORD_123'})
        self.assertEqual(result.status_code,200);return result.json()['access_token']

    def submit(self,**values):return self.client.post('/listings',json=VALID|values,headers=self.headers)

    def count(self):
        with self.database.session() as session:return session.scalar(select(func.count()).select_from(Listing))

    def test_valid_pending_own_dto_categories_and_exact_persistence(self):
        result=self.submit(title='  Useful book  ',description='  A useful textbook.  ',price='12.3400')
        self.assertEqual(result.status_code,201);data=result.json();self.assertEqual(set(data),FIELDS)
        self.assertIsInstance(data['id'],int);self.assertEqual(data['title'],'Useful book');self.assertEqual(data['description'],'A useful textbook.')
        self.assertEqual((data['price'],data['currency'],data['status'],data['published_at']),('12.34','KZT','pending',None))
        self.assertIsNotNone(datetime.fromisoformat(data['created_at']).tzinfo)
        with self.database.session() as session:
            listing=session.get(Listing,data['id']);self.assertEqual(listing.owner_id,self.user.id);self.assertEqual(listing.price,Decimal('12.34'));self.assertIsNone(listing.rejection_reason)
        categories=self.client.get('/categories',headers=self.headers)
        self.assertEqual(categories.status_code,200);self.assertEqual(categories.json(),[{'id':id,'key':key,'label':label} for id,key,label in CATEGORIES])
        self.assertNotIn(self.user.phone,result.text);self.assertNotIn(self.user.email,result.text)

    def test_text_required_type_length_category_and_condition_validation(self):
        invalid=[{'title':'ab'},{'title':'x'*121},{'title':None},{'title':123},{'title':'bad\x00title'},{'description':'   '},{'description':'x'*9},{'description':'x'*2001},{'description':None},{'description':True},{'description':'bad\x00description'},{'category_id':0},{'category_id':6},{'category_id':'1'},{'category_id':True},{'category_id':1.0},{'category_id':None},{'condition':'New'},{'condition':'broken'},{'condition':None},{'condition':1}]
        for values in invalid:
            with self.subTest(fields=tuple(values)):
                response=self.submit(**values);self.assertEqual(response.status_code,422);self.assertEqual(response.json(),{'detail':'Invalid listing request.'})
        for key in VALID:
            payload=VALID.copy();del payload[key]
            self.assertEqual(self.client.post('/listings',json=payload,headers=self.headers).status_code,422)
        self.assertEqual(self.count(),0)
        self.assertEqual(self.submit(title='x'*3,description='x'*10).status_code,201)
        self.assertEqual(self.submit(title='x'*120,description='x'*2000,category_id=5,condition='new').status_code,201)

    def test_decimal_boundaries_number_string_meaningful_precision_and_exact_json(self):
        for price,expected in [(0,'0.00'),(1000000000,'1000000000.00'),(12.34,'12.34'),('0.0100','0.01'),('1.2300','1.23'),('1000000000.00','1000000000.00')]:
            result=self.submit(price=price);self.assertEqual(result.status_code,201);self.assertEqual(result.json()['price'],expected)
        before=self.count()
        for price in [True,False,None,-1,'-1','NaN','Infinity','1e2','+1','01',' 1','1.','.1','0x10','1,20','1.005','0.001','1000000000.01',[],{}]:
            self.assertEqual(self.submit(price=price).status_code,422)
        self.assertEqual(self.count(),before)
        for number in ['1.00000000000000001','NaN','Infinity','-Infinity','1e999999']:
            raw=json.dumps(VALID).replace('"12.34"',number)
            self.assertEqual(self.client.post('/listings',content=raw,headers=self.headers|{'Content-Type':'application/json'}).status_code,422)
        raw=json.dumps(VALID).replace('"12.34"','1e2')
        self.assertEqual(self.client.post('/listings',content=raw,headers=self.headers|{'Content-Type':'application/json'}).json()['price'],'100.00')

    def test_protected_fields_and_malformed_duplicate_json_cannot_select_owner_or_publish(self):
        for key in ['owner_id','id','status','currency','published_at','rejection_reason','photos','user_id']:
            self.assertEqual(self.submit(**{key:self.other.id}).status_code,422)
        for content in ['{','[]','null',json.dumps(VALID)[:-1]+',"title":"Other"}']:
            self.assertEqual(self.client.post('/listings',content=content,headers=self.headers|{'Content-Type':'application/json'}).status_code,422)
        self.assertEqual(self.client.post('/listings',content=json.dumps(VALID),headers=self.headers|{'Content-Type':'text/plain'}).status_code,422)
        self.assertEqual(self.count(),0)
        with self.database.session() as session:self.assertIsNone(session.get(User,self.other.id).name)

    def test_contact_required_revalidates_legacy_values_and_accepts_any_one_valid_contact_without_name(self):
        for contacts in [{'phone':None,'telegram_username':None,'external_contact_url':None},{'phone':'bad','telegram_username':'@bad','external_contact_url':'javascript:bad'}]:
            with self.database.session() as session:
                user=session.get(User,self.user.id)
                for field,value in contacts.items():setattr(user,field,value)
            result=self.submit();self.assertEqual(result.status_code,400);self.assertEqual(result.json(),{'detail':'Add a valid contact method to your profile before creating a listing.'})
        self.assertEqual(self.count(),0)
        for field,value in [('phone','+77001234567'),('telegram_username','valid_user'),('external_contact_url','https://example.test/contact')]:
            with self.database.session() as session:
                user=session.get(User,self.user.id)
                user.phone=user.telegram_username=user.external_contact_url=None;setattr(user,field,value)
                self.assertIsNone(user.name)
            self.assertEqual(self.submit().status_code,201)

    def test_missing_ineligible_revoked_expired_and_deleted_cannot_use_endpoints(self):
        self.assertEqual(self.client.post('/listings',json=VALID).status_code,401);self.assertEqual(self.client.get('/categories').status_code,401)
        for flag in ['verified','suspended']:
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='suspended')
            self.assertEqual(self.submit().status_code,401);self.assertEqual(self.client.get('/categories',headers=self.headers).status_code,401)
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='verified')
        with self.database.session() as session:revoke_user_sessions(session,self.user.id,self.now)
        self.assertEqual(self.submit().status_code,401);self.assertEqual(self.client.get('/categories',headers=self.headers).status_code,401)
        self.headers={'Authorization':'Bearer '+self.login()};self.now+=timedelta(minutes=15)
        self.assertEqual(self.submit().status_code,401)
        self.now-=timedelta(minutes=15)
        with self.database.session() as session:session.delete(session.get(User,self.user.id))
        self.assertEqual(self.submit().status_code,401);self.assertEqual(self.client.get('/categories',headers=self.headers).status_code,401);self.assertEqual(self.count(),0)

    def test_commit_failure_rolls_back_and_returns_sanitized_errors(self):
        original=Session.commit
        def fail_listing_commit(session):
            if session.scalar(select(func.count()).select_from(Listing))>0:raise SQLAlchemyError('SENSITIVE_DRIVER_TOKEN')
            return original(session)
        with patch.object(Session,'commit',fail_listing_commit):result=self.submit()
        self.assertEqual(result.status_code,500);self.assertEqual(result.json(),{'detail':'Listings are temporarily unavailable.'});self.assertEqual(self.count(),0)
        self.assertEqual(self.submit().status_code,201)

    def test_stale_guard_cannot_create_after_revocation_suspension_or_contact_removal(self):
        for mutation,expected in [('contact',400),('suspend',401),('revoke',401)]:
            self.headers={'Authorization':'Bearer '+self.login()};ready,release=Event(),Event()
            def paused(*args,**kwargs):
                ready.set()
                if not release.wait(5):raise RuntimeError('Test synchronization timed out')
                return create_own_listing(*args,**kwargs)
            with patch('backend.routers.listings.create_own_listing',side_effect=paused):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending=executor.submit(self.submit);self.assertTrue(ready.wait(5))
                    try:
                        with self.database.session() as session:
                            user=session.get(User,self.user.id)
                            if mutation=='contact':user.phone=None
                            elif mutation=='suspend':user.suspended=True
                            else:revoke_user_sessions(session,user.id,self.now)
                    finally:release.set()
                    self.assertEqual(pending.result(timeout=5).status_code,expected)
            with self.database.session() as session:
                user=session.get(User,self.user.id);user.phone='+77001234567';user.suspended=False
        self.assertEqual(self.count(),0)
