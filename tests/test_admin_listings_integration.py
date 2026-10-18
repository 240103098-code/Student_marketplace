from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.admin import promote_existing_admin
from backend.admin_listings import remove_admin_listing
from backend.models import Listing,ListingPhoto,User
from backend.sessions import revoke_user_sessions

class AdminListingsPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 snapshot=fixture.SoldPostgreSQLTest.snapshot
 def setUp(self):fixture.SoldPostgreSQLTest.setUp(self);promote_existing_admin(self.database,self.buyer.email)
 def remove(self,headers=None):return self.client.post(f'/admin/listings/{self.item.id}/remove',headers=self.buyer_headers if headers is None else headers)
 def detail(self):return self.client.get(f'/admin/listings/{self.item.id}',headers=self.buyer_headers)
 def state(self,state):
  with self.database.session() as s:row=s.get(Listing,self.item.id);row.status=state;row.published_at=self.now if state in ['active','sold'] else None;row.rejection_reason='Private review reason' if state=='rejected' else None
 def test_all_states_status_paging_suspended_seller_and_minimal_dtos(self):
  for state in ['pending','active','sold','rejected','removed']:
   self.state(state);result=self.client.get('/admin/listings?status='+state,headers=self.buyer_headers);self.assertEqual(result.status_code,200);self.assertEqual(result.json()['total'],1);self.assertEqual(result.json()['items'][0]['status'],state);detail=self.detail();self.assertEqual(detail.status_code,200);self.assertEqual(set(detail.json()['seller']),{'id','email','name'});self.assertEqual(detail.json()['rejection_reason'],'Private review reason' if state=='rejected' else None)
   for forbidden in ['password_hash','storage_path','telegram_username','phone','avatar_path','verified','suspended','token']:self.assertNotIn(forbidden,detail.text)
  with self.database.session() as s:
   extra=Listing(owner_id=self.owner.id,category_id=1,title='Extra listing',description='Another useful item.',price=self.item.price,condition='used',status='pending',created_at=self.item.created_at);s.add(extra);s.flush();extra_id=extra.id;s.get(User,self.owner.id).suspended=True
  first=self.client.get('/admin/listings?limit=1',headers=self.buyer_headers).json();self.assertEqual(first['total'],2);self.assertEqual(first['items'][0]['id'],extra_id);self.assertEqual(self.client.get('/admin/listings?limit=1&offset=1',headers=self.buyer_headers).json()['items'][0]['id'],self.item.id)
  self.assertEqual(self.detail().status_code,200);self.assertEqual(self.client.get('/admin/listings?offset=9223372036854775807',headers=self.buyer_headers).json()['items'],[])
  for query in ['limit=0','limit=51','offset=-1','status=','status=private','status=active&status=sold','owner_id=1','sort=id','offset=9223372036854775808']:
   self.assertEqual(self.client.get('/admin/listings?'+query,headers=self.buyer_headers).status_code,422)
 def test_admin_photos_linkage_all_states_private_and_no_buyer_permission_widening(self):
  for state in ['pending','active','sold','rejected','removed']:
   self.state(state);url=self.detail().json()['photos'][0]['url'];result=self.client.get(url,headers=self.buyer_headers);self.assertEqual(result.status_code,200);self.assertEqual(result.headers['cache-control'],'private, no-store');self.assertEqual(result.headers['x-content-type-options'],'nosniff');self.assertTrue(result.content.startswith(b'\x89PNG'))
   self.assertEqual(self.client.get(url,headers=self.headers).status_code,403);self.assertEqual(self.client.get(url).status_code,401)
   if state!='active':self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.buyer_headers).status_code,404)
  self.assertEqual(self.client.get(f'/admin/listings/{self.item.id}/photos/{self.photo.id+100}',headers=self.buyer_headers).status_code,404)
  with self.database.session() as s:
   other=Listing(owner_id=self.owner.id,category_id=1,title='Other photo listing',description='A different listing.',price=self.item.price,condition='used',status='pending');s.add(other);s.flush();wrong=ListingPhoto(listing_id=other.id,position=1,storage_path=f'listings/{other.id}/'+ 'f'*32+'.png');s.add(wrong);s.flush();wrong_id=wrong.id
  self.assertEqual(self.client.get(f'/admin/listings/{self.item.id}/photos/{wrong_id}',headers=self.buyer_headers).status_code,404)
  self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.headers).status_code,404)
 def test_remove_all_states_idempotence_retains_files_reports_and_buyer_exclusion(self):
  with self.database.session() as s:
   other=Listing(owner_id=self.owner.id,category_id=1,title='Unrelated listing',description='Preserve this listing.',price=self.item.price,condition='used',status='pending');s.add(other);s.flush();other_id=other.id
  for state in ['pending','active','sold','rejected','removed']:
   self.state(state);before=self.snapshot();published=self.detail().json()['published_at'];reason=self.detail().json()['rejection_reason']
   for _ in range(2):
    result=self.remove();self.assertEqual(result.status_code,200);self.assertEqual(result.json(),{'id':self.item.id,'status':'removed','published_at':published})
   self.assertEqual(self.snapshot(),before)
   with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).rejection_reason,reason)
   self.assertEqual(self.client.get('/listings',headers=self.buyer_headers).json()['total'],0);self.assertEqual(self.client.get(f'/listings/{self.item.id}',headers=self.buyer_headers).status_code,404);self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.headers).status_code,404);self.assertEqual(self.detail().json()['status'],'removed');self.assertEqual(next(r for r in self.client.get('/listings/mine',headers=self.headers).json()['items'] if r['id']==self.item.id)['status'],'removed')
   with self.database.session() as s:self.assertEqual(s.get(Listing,other_id).status,'pending')
 def test_payload_bounded_ids_guards_and_failed_commit_preservation(self):
  for body in [{'status':'removed'},{'reason':'unsafe'},{'owner_id':1},None,[]]:self.assertEqual(self.client.post(f'/admin/listings/{self.item.id}/remove',json=body,headers=self.buyer_headers).status_code,422 if body is not None else 200)
  self.assertEqual(self.client.post(f'/admin/listings/{self.item.id}/remove',content='null',headers=self.buyer_headers).status_code,422)
  self.state('active');self.assertEqual(self.remove(self.headers).status_code,403);self.assertEqual(self.remove({}).status_code,401)
  for id in [0,2**63]:self.assertEqual(self.client.post(f'/admin/listings/{id}/remove',headers=self.buyer_headers).status_code,422)
  before=self.snapshot();original=Session.commit
  def fail(s):
   if s.get(Listing,self.item.id).status=='removed':raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):self.assertEqual(self.remove().status_code,500)
  self.assertEqual(self.snapshot(),before)
  with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).status,'active')
 def test_stale_demoted_or_revoked_admin_does_not_remove(self):
  for change in ['role','suspend','revoke']:
   ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return remove_admin_listing(*a,**k)
   with patch('backend.routers.admin.remove_admin_listing',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.remove);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      if change=='role':s.get(User,self.buyer.id).role='student'
      elif change=='suspend':s.get(User,self.buyer.id).suspended=True
      else:revoke_user_sessions(s,self.buyer.id,self.now)
     release.set();self.assertEqual(future.result(timeout=5).status_code,403 if change=='role' else 401)
   with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).status,'active');s.get(User,self.buyer.id).role='admin';s.get(User,self.buyer.id).suspended=False
 def test_racing_seller_sold_or_delete_is_rechecked_without_restore(self):
  for action in ['sold','delete']:
   ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return remove_admin_listing(*a,**k)
   with patch('backend.routers.admin.remove_admin_listing',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.remove);self.assertTrue(ready.wait(5));result=self.client.post(f'/listings/{self.item.id}/sold',headers=self.headers) if action=='sold' else self.client.delete(f'/listings/{self.item.id}',headers=self.headers);self.assertEqual(result.status_code,200);release.set();self.assertEqual(future.result(timeout=5).status_code,200 if action=='sold' else 404)
   if action=='sold':
    self.assertEqual(self.detail().json()['status'],'removed');self.state('active')
