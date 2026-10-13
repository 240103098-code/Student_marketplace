from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.images import ImageStorage, canonical_image
from backend.listings import mark_own_listing_sold
from backend.models import Listing, ListingPhoto, ListingReport, User
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database
from test_avatar_integration import picture

class SoldPostgreSQLTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.settings,cls.database,_=open_disposable_database();cls.addClassCleanup(cls.database.dispose)
  cls.cfg=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.cfg.attributes['settings']=cls.settings;command.upgrade(cls.cfg,'head');cls.addClassCleanup(command.downgrade,cls.cfg,'0001_baseline')
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='sold-disposable-');self.settings=self.settings.model_copy(update={'upload_dir':Path(self.temp.name)})
  self.now=datetime(2026,10,12,12,tzinfo=timezone.utc);self.context=TestClient(create_app(self.settings,self.database,clock=lambda:self.now));self.client=self.context.__enter__()
  with self.database.session() as s:
   self.owner=User(email='seller@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_SOLD_PASSWORD_123'),verified=True);self.buyer=User(email='buyer@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_SOLD_PASSWORD_123'),verified=True);s.add_all([self.owner,self.buyer]);s.flush()
   self.item=Listing(owner_id=self.owner.id,category_id=1,title='Useful book',description='A useful textbook.',price=Decimal('12.34'),condition='used',status='active',published_at=self.now);s.add(self.item);s.flush()
   path=ImageStorage(self.settings.upload_dir,'listings').write(canonical_image(picture()),self.item.id);self.photo=ListingPhoto(listing_id=self.item.id,storage_path=path,position=1);s.add(self.photo);s.add(ListingReport(listing_id=self.item.id,reporter_id=self.buyer.id,reason='spam'));s.flush()
  self.headers={'Authorization':'Bearer '+self.login(self.owner.email)};self.buyer_headers={'Authorization':'Bearer '+self.login(self.buyer.email)}
 def tearDown(self):
  self.context.__exit__(None,None,None)
  with self.database.session() as s:s.execute(delete(User))
  self.temp.cleanup()
 def login(self,email):return self.client.post('/auth/login',json={'email':email,'password':'TEST_SOLD_PASSWORD_123'}).json()['access_token']
 def sold(self,headers=None):return self.client.post(f'/listings/{self.item.id}/sold',headers=self.headers if headers is None else headers)
 def snapshot(self):
  with self.database.session() as s:
   item=s.get(Listing,self.item.id);return {key:getattr(item,key) for key in ['title','description','price','category_id','condition','owner_id','created_at','published_at']},[(p.id,p.position,p.storage_path) for p in s.scalars(select(ListingPhoto))],[(r.id,r.reason) for r in s.scalars(select(ListingReport))],[(str(p),p.read_bytes()) for p in Path(self.temp.name).rglob('*') if p.is_file()]
 def test_transition_idempotence_preserved_data_dashboard_and_private_bytes(self):
  before=self.snapshot();url=f'/listings/{self.item.id}/photos/{self.photo.id}'
  self.assertEqual(self.client.get(url,headers=self.buyer_headers).status_code,200)
  for _ in range(2):self.assertEqual(self.sold().json()['status'],'sold')
  self.assertEqual(self.snapshot(),before);self.assertEqual(self.client.get('/listings/mine?status=active',headers=self.headers).json()['total'],0);self.assertEqual(self.client.get('/listings/mine?status=sold',headers=self.headers).json()['total'],1)
  self.assertEqual(self.client.get(url,headers=self.buyer_headers).status_code,404);self.assertEqual(self.client.get(url,headers=self.headers).status_code,200)
 def test_concurrent_sold_is_idempotent(self):
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.sold(),range(2)))
  self.assertEqual([r.status_code for r in results],[200,200])
 def test_forbidden_states_and_ownership(self):
  self.assertEqual(self.sold(self.buyer_headers).status_code,404)
  for state in ['pending','rejected','removed']:
   with self.database.session() as s:item=s.get(Listing,self.item.id);item.status=state;item.published_at=None;item.rejection_reason='Rejected.' if state=='rejected' else None
   self.assertEqual(self.sold().status_code,409)
   with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).status,state)
 def test_invalid_fields_ids_and_revoked_ineligible(self):
  for body in [{'status':'sold'},{'owner_id':self.buyer.id},None,[]]:self.assertEqual(self.client.post(f'/listings/{self.item.id}/sold',content=__import__('json').dumps(body),headers=self.headers).status_code,422)
  for id in [0,2**63]:self.assertEqual(self.client.post(f'/listings/{id}/sold',headers=self.headers).status_code,422)
  self.assertEqual(self.client.post(f'/listings/{self.item.id}/sold').status_code,401)
  with self.database.session() as s:s.get(User,self.owner.id).suspended=True
  self.assertEqual(self.sold().status_code,401)
  with self.database.session() as s:s.get(User,self.owner.id).suspended=False;revoke_user_sessions(s,self.owner.id,self.now)
  self.assertEqual(self.sold().status_code,401)
 def test_stale_state_and_session_rechecked(self):
  ready,release=Event(),Event()
  def pause(*args,**kwargs):ready.set();release.wait(5);return mark_own_listing_sold(*args,**kwargs)
  with patch('backend.routers.listings.mark_own_listing_sold',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.sold);self.assertTrue(ready.wait(5))
    with self.database.session() as s:revoke_user_sessions(s,self.owner.id,self.now)
    release.set();self.assertEqual(future.result(timeout=5).status_code,401)
 def test_commit_failure_rolls_back(self):
  original=Session.commit
  def fail(s):
   item=s.get(Listing,self.item.id)
   if item and item.status=='sold':raise SQLAlchemyError('SENSITIVE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):self.assertEqual(self.sold().status_code,500)
  with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).status,'active')
