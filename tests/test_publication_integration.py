from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
import unittest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.admin import promote_existing_admin
from backend.publication import decide_publication
from backend.models import User,Listing
from backend.sessions import revoke_user_sessions
from test_avatar_integration import picture

class PublicationPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 snapshot=fixture.SoldPostgreSQLTest.snapshot
 def setUp(self):
  fixture.SoldPostgreSQLTest.setUp(self);promote_existing_admin(self.database,self.buyer.email)
  with self.database.session() as s:
   reader=User(email='reader@sdu.edu.kz',password_hash=self.owner.password_hash,verified=True);s.add(reader)
  self.reader={'Authorization':'Bearer '+self.login('reader@sdu.edu.kz')}
 def pending(self,photo=False):
  self.assertEqual(self.client.patch('/users/me',headers=self.headers,json={'phone':'+77001234567'}).status_code,200)
  response=self.client.post('/listings',headers=self.headers,json={'title':'Pending campus textbook','description':'A useful campus textbook for another student.','price':'10.10','category_id':1,'condition':'used'});self.assertEqual(response.status_code,201);id=response.json()['id']
  if photo:
   image=self.client.post(f'/listings/{id}/photos',headers=self.headers,files={'image':('image.png',picture(),'image/png')});self.assertEqual(image.status_code,201)
  return id
 def approve(self,id,headers=None):return self.client.post(f'/admin/listings/{id}/approve',headers=self.buyer_headers if headers is None else headers)
 def reject(self,id,reason='Please improve the description.',headers=None):return self.client.post(f'/admin/listings/{id}/reject',headers=self.buyer_headers if headers is None else headers,json={'reason':reason})
 def get(self,id):
  with self.database.session() as s:return s.get(Listing,id)
 def test_real_pending_photo_to_manual_approval_visibility_and_retained_edit_approval(self):
  id=self.pending(photo=True);private=self.client.get(f'/admin/listings/{id}',headers=self.buyer_headers).json();photo_id=private['photos'][0]['id']
  self.assertNotIn(id,[r['id'] for r in self.client.get('/listings',headers=self.reader).json()['items']]);self.assertEqual(self.client.get(f'/listings/{id}',headers=self.reader).status_code,404);self.assertEqual(self.client.get(f'/listings/{id}/photos/{photo_id}',headers=self.reader).status_code,404)
  approved=self.approve(id);self.assertEqual(approved.status_code,200);self.assertEqual(self.get(id).published_at,self.now);self.assertEqual(self.get(id).status,'active');self.assertIn(id,[r['id'] for r in self.client.get('/listings',headers=self.reader).json()['items']]);self.assertEqual(self.client.get(f'/listings/{id}',headers=self.reader).status_code,200);self.assertEqual(self.client.get(f'/listings/{id}/photos/{photo_id}',headers=self.reader).status_code,200)
  self.client.app.state.clock=lambda:self.now+timedelta(seconds=20);self.assertEqual(self.approve(id).json(),approved.json());self.assertEqual(self.client.patch(f'/listings/{id}',headers=self.headers,json={'price':'11.11','description':'A clearer description of this useful textbook.'}).status_code,200);self.assertEqual(self.get(id).published_at,self.now);self.assertEqual(self.get(id).status,'active');self.assertEqual(self.client.post(f'/listings/{id}/photos',headers=self.headers,files={'image':('image.png',picture(),'image/png')}).status_code,409)
  self.assertEqual(self.client.post(f'/listings/{id}/sold',headers=self.headers).status_code,200);self.assertEqual(self.approve(id).status_code,409);self.assertEqual(self.client.post(f'/admin/listings/{id}/remove',headers=self.buyer_headers).status_code,200);self.assertEqual(self.approve(id).status_code,409);self.assertEqual(self.get(id).published_at,self.now)
 def test_rejection_owner_feedback_private_images_identical_retry_and_conflict(self):
  id=self.pending(photo=True);response=self.reject(id,'  Use a clearer title.  ');self.assertEqual(response.status_code,200);self.assertEqual(response.json()['rejection_reason'],'Use a clearer title.');self.assertIsNone(self.get(id).published_at);self.assertEqual(self.reject(id,'Use a clearer title.').json(),response.json());self.assertEqual(self.reject(id,'Another reason.').status_code,409);self.assertEqual(self.approve(id).status_code,409)
  owner=next(r for r in self.client.get('/listings/mine',headers=self.headers).json()['items'] if r['id']==id);self.assertEqual(owner['status'],'rejected');self.assertEqual(owner['rejection_reason'],'Use a clearer title.');self.assertEqual(self.client.get(f'/listings/{id}',headers=self.reader).status_code,404);self.assertEqual(self.client.get(owner['photos'][0]['url'],headers=self.reader).status_code,404);self.assertEqual(self.client.patch(f'/listings/{id}',headers=self.headers,json={'price':'20'}).status_code,409)
 def test_strict_reason_payload_bounds_and_ordinary_user_bypass(self):
  id=self.pending();self.assertEqual(self.approve(id,self.reader).status_code,403);self.assertEqual(self.reject(id,headers=self.reader).status_code,403)
  for body in [{},{'reason':''},{'reason':'  '},{'reason':True},{'reason':1},{'reason':None},{'reason':'x'*301},{'reason':'a\x00b'},{'reason':'x','status':'rejected'},{'reason':'x','owner_id':self.owner.id}]:self.assertEqual(self.client.post(f'/admin/listings/{id}/reject',headers=self.buyer_headers,json=body).status_code,422)
  for body in [{'status':'active'},{'published_at':'now'},{'owner_id':self.owner.id}]:self.assertEqual(self.client.post(f'/admin/listings/{id}/approve',headers=self.buyer_headers,json=body).status_code,422)
  self.assertEqual(self.client.post(f'/admin/listings/{id}/approve',headers=self.buyer_headers,content='null').status_code,422)
  self.assertEqual(self.reject(id,'  '+'x'*300+'  ').status_code,200);self.assertEqual(len(self.get(id).rejection_reason),300)
  for bad in [0,2**63]:self.assertEqual(self.approve(bad).status_code,422)
  self.assertEqual(self.approve(9223372036854775807).status_code,404)
 def test_ineligible_seller_cannot_be_published_but_can_receive_rejection(self):
  id=self.pending()
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,value)
   self.assertEqual(self.approve(id).status_code,409);self.assertEqual(self.get(id).status,'pending')
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,not value)
  with self.database.session() as s:s.get(User,self.owner.id).suspended=True
  self.assertEqual(self.reject(id).status_code,200)
 def test_decision_commit_failure_preserves_content_photos_and_other_listing(self):
  id=self.pending(photo=True);before=self.snapshot();original=Session.commit
  for action in ['approve','reject']:
   def fail(s):
    if s.get(Listing,id).status!='pending':raise SQLAlchemyError('PRIVATE_DRIVER')
    return original(s)
   with patch.object(Session,'commit',fail):self.assertEqual((self.approve(id) if action=='approve' else self.reject(id)).status_code,500)
   self.assertEqual(self.get(id).status,'pending');self.assertIsNone(self.get(id).published_at);self.assertIsNone(self.get(id).rejection_reason);self.assertEqual(self.snapshot(),before)
 def test_two_admins_approve_reject_race_and_repeat_approval(self):
  id=self.pending();promote_existing_admin(self.database,'reader@sdu.edu.kz')
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda h:self.approve(id,h),[self.buyer_headers,self.reader]))
  self.assertEqual([r.status_code for r in results],[200,200]);self.assertEqual(results[0].json(),results[1].json())
  second=self.pending()
  with ThreadPoolExecutor(max_workers=2) as pool:
   approve=pool.submit(self.approve,second);reject=pool.submit(self.reject,second,'A different review.',self.reader);results=[approve.result(timeout=5),reject.result(timeout=5)]
  self.assertEqual(sorted(r.status_code for r in results),[200,409]);self.assertIn(self.get(second).status,['active','rejected'])
 def test_suspension_or_seller_edit_delete_removal_before_decision_is_rechecked(self):
  for change in ['edit','suspend','remove','delete']:
   id=self.pending();ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return decide_publication(*a,**k)
   with patch('backend.routers.admin.decide_publication',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.approve,id);self.assertTrue(ready.wait(5))
     if change=='edit':self.assertEqual(self.client.patch(f'/listings/{id}',headers=self.headers,json={'price':'15.15'}).status_code,200)
     elif change=='suspend':self.assertEqual(self.client.patch(f'/admin/users/{self.owner.id}/suspension',headers=self.buyer_headers,json={'suspended':True}).status_code,200)
     elif change=='remove':self.assertEqual(self.client.post(f'/admin/listings/{id}/remove',headers=self.buyer_headers).status_code,200)
     else:self.assertEqual(self.client.delete(f'/listings/{id}',headers=self.headers).status_code,200)
     release.set();self.assertEqual(future.result(timeout=5).status_code,200 if change=='edit' else 404 if change=='delete' else 409)
   if change=='edit':self.assertEqual(str(self.get(id).price),'15.15')
   if change=='suspend':
    self.assertEqual(self.client.patch(f'/admin/users/{self.owner.id}/suspension',headers=self.buyer_headers,json={'suspended':False}).status_code,200);self.headers={'Authorization':'Bearer '+self.login(self.owner.email)}
 def test_stale_demoted_or_revoked_admin_cannot_decide(self):
  id=self.pending()
  for change in ['role','revoke']:
   ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return decide_publication(*a,**k)
   with patch('backend.routers.admin.decide_publication',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.approve,id);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      if change=='role':s.get(User,self.buyer.id).role='student'
      else:revoke_user_sessions(s,self.buyer.id,self.now)
     release.set();self.assertEqual(future.result(timeout=5).status_code,403 if change=='role' else 401)
   self.assertEqual(self.get(id).status,'pending')
   with self.database.session() as s:s.get(User,self.buyer.id).role='admin'
