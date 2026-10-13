from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
from threading import Event
import unittest
from unittest.mock import patch
import uuid

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.listings import update_own_listing
from backend.models import Listing, ListingPhoto, User
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database


class ListingEditPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings,cls.database,_=open_disposable_database();cls.addClassCleanup(cls.database.dispose)
        cls.configuration=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.configuration.attributes['settings']=cls.settings
        command.upgrade(cls.configuration,'head');cls.addClassCleanup(command.downgrade,cls.configuration,'0001_baseline')

    def setUp(self):
        self.now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        self.context=TestClient(create_app(self.settings,self.database,clock=lambda:self.now));self.client=self.context.__enter__()
        with self.database.session() as session:
            self.user=User(email='seller@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_EDIT_PASSWORD_123'),verified=True)
            self.other=User(email='other@sdu.edu.kz',password_hash='SYNTHETIC_HASH',verified=True)
            session.add_all([self.user,self.other]);session.flush()
            self.listing=Listing(owner_id=self.user.id,title='Original title',description='Original description.',price=Decimal('12.34'),category_id=1,condition='used')
            self.other_listing=Listing(owner_id=self.other.id,title='Other title',description='Other description.',price=Decimal('2.00'),category_id=2,condition='new')
            session.add_all([self.listing,self.other_listing]);session.flush()
            photo=ListingPhoto(listing_id=self.listing.id,storage_path=f'listings/{self.listing.id}/{uuid.uuid4().hex}.png',position=1)
            session.add(photo);session.flush()
        self.headers={'Authorization':'Bearer '+self.login()}

    def tearDown(self):
        self.context.__exit__(None,None,None)
        with self.database.session() as session:session.execute(delete(User))

    def login(self):return self.client.post('/auth/login',json={'email':self.user.email,'password':'TEST_EDIT_PASSWORD_123'}).json()['access_token']
    def read(self,id=None):return self.client.get(f'/listings/{self.listing.id if id is None else id}/edit',headers=self.headers)
    def edit(self,payload,id=None):return self.client.patch(f'/listings/{self.listing.id if id is None else id}',json=payload,headers=self.headers)
    def state(self,value):
        with self.database.session() as session:
            listing=session.get(Listing,self.listing.id);listing.status=value;listing.published_at=self.now if value in {'active','sold'} else None;listing.rejection_reason='Not permitted.' if value=='rejected' else None
    def immutable(self):
        with self.database.session() as session:
            item=session.get(Listing,self.listing.id)
            photos=list(session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id==item.id)))
            return (item.owner_id,item.title,item.category_id,item.condition,item.status,item.created_at,item.published_at,item.rejection_reason),[(p.id,p.position,p.storage_path) for p in photos]

    def test_owner_current_edit_shape_and_nonowner_missing_are_private(self):
        response=self.read();self.assertEqual(response.status_code,200)
        self.assertEqual(set(response.json()),{'id','title','price','description','status','published_at'})
        self.assertEqual(response.json()['price'],'12.34');self.assertIsNone(response.json()['published_at'])
        for id in [self.other_listing.id,999999]:
            self.assertEqual(self.read(id).status_code,404);self.assertEqual(self.edit({'price':'1.00'},id).status_code,404)
        self.assertNotIn('storage_path',response.text);self.assertNotIn(self.user.email,response.text)

    def test_pending_active_sold_allow_partial_changes_and_preserve_every_immutable_field(self):
        for state in ['pending','active','sold']:
            self.state(state);before=self.immutable()
            response=self.edit({'price':'15.6700'});self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['price'],'15.67');self.assertEqual(response.json()['description'],'Original description.')
            response=self.edit({'description':'  Updated description.  '});self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['description'],'Updated description.');self.assertEqual(response.json()['price'],'15.67')
            self.assertEqual(self.immutable(),before)
            self.edit({'description':'Original description.','price':'12.34'})
        with self.database.session() as session:
            other=session.get(Listing,self.other_listing.id);self.assertEqual(other.price,Decimal('2.00'));self.assertEqual(other.description,'Other description.')

    def test_rejected_removed_have_safe_read_but_cannot_mutate(self):
        for state in ['rejected','removed']:
            self.state(state);before=self.immutable()
            self.assertEqual(self.read().json()['status'],state)
            result=self.edit({'price':'1.00','description':'Must not be saved.'});self.assertEqual(result.status_code,409)
            self.assertEqual(self.immutable(),before)
            with self.database.session() as session:self.assertEqual(session.get(Listing,self.listing.id).price,Decimal('12.34'))

    def test_null_empty_protected_and_malformed_values_are_rejected_without_partial_update(self):
        before=self.read().json()
        invalid=[{}, {'price':None},{'description':None},{'price':True},{'description':1},{'description':' '},{'description':'x'*9},{'description':'x'*2001},{'price':'1.005'},{'price':'-1'},{'price':'1000000000.01'},{'price':'NaN'},{'price':'1e2'},{'price':'01'}]
        for key in ['title','category_id','condition','photos','owner_id','status','currency','created_at','published_at','rejection_reason','id']:
            invalid.append({'price':'9.00',key:'MUST_NOT_SAVE'})
        for payload in invalid:
            self.assertEqual(self.edit(payload).status_code,422);self.assertEqual(self.read().json(),before)
        for raw in ['{"price":NaN}','{"price":1.00000000000000001}','{"price":"9.00","price":"10.00"}','[]','{']:
            result=self.client.patch(f'/listings/{self.listing.id}',content=raw,headers=self.headers|{'Content-Type':'application/json'})
            self.assertEqual(result.status_code,422);self.assertEqual(result.json(),{'detail':'Invalid listing-edit request.'})
        self.assertEqual(self.read().json(),before)

    def test_exact_price_and_description_boundaries(self):
        for price,expected in [(0,'0.00'),(1000000000,'1000000000.00'),('0.0100','0.01'),(12.34,'12.34')]:
            result=self.edit({'price':price});self.assertEqual(result.status_code,200);self.assertEqual(result.json()['price'],expected)
        for value in ['x'*10,'x'*2000]:self.assertEqual(self.edit({'description':value}).status_code,200)

    def test_actual_commit_failure_rolls_back_both_fields(self):
        before=self.read().json();original=Session.commit
        def fail_changed(session):
            item=session.get(Listing,self.listing.id)
            if item and item.price==Decimal('77.00'):raise SQLAlchemyError('SENSITIVE_DRIVER')
            return original(session)
        with patch.object(Session,'commit',fail_changed):result=self.edit({'price':'77.00','description':'Must roll back.'})
        self.assertEqual(result.status_code,500);self.assertEqual(result.json(),{'detail':'Listings are temporarily unavailable.'})
        self.assertEqual(self.read().json(),before)

    def test_missing_ineligible_and_revoked_access_cannot_read_or_edit(self):
        self.assertEqual(self.client.get(f'/listings/{self.listing.id}/edit').status_code,401)
        self.assertEqual(self.client.patch(f'/listings/{self.listing.id}',json={'price':'1.00'}).status_code,401)
        for flag in ['verified','suspended']:
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='suspended')
            self.assertEqual(self.read().status_code,401);self.assertEqual(self.edit({'price':'1.00'}).status_code,401)
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='verified')
        with self.database.session() as session:revoke_user_sessions(session,self.user.id,self.now)
        self.assertEqual(self.read().status_code,401);self.assertEqual(self.edit({'price':'1.00'}).status_code,401)

    def test_stale_guard_rechecks_state_ownership_and_revocation(self):
        for mutation,expected in [('state',409),('owner',404),('revoke',401)]:
            self.headers={'Authorization':'Bearer '+self.login()};ready,release=Event(),Event()
            def paused(*args,**kwargs):
                ready.set()
                if not release.wait(5):raise RuntimeError('Test synchronization timed out')
                return update_own_listing(*args,**kwargs)
            with patch('backend.routers.listings.update_own_listing',side_effect=paused):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending=executor.submit(self.edit,{'price':'99.00'});self.assertTrue(ready.wait(5))
                    try:
                        with self.database.session() as session:
                            item=session.get(Listing,self.listing.id)
                            if mutation=='state':item.status='rejected';item.rejection_reason='Not permitted.'
                            elif mutation=='owner':item.owner_id=self.other.id
                            else:revoke_user_sessions(session,self.user.id,self.now)
                    finally:release.set()
                    self.assertEqual(pending.result(timeout=5).status_code,expected)
            with self.database.session() as session:
                item=session.get(Listing,self.listing.id);self.assertEqual(item.price,Decimal('12.34'));item.owner_id=self.user.id;item.status='pending';item.rejection_reason=None
