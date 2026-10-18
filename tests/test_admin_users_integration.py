from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import patch
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.admin import promote_existing_admin
from backend.admin_users import set_student_suspension
from backend.models import User,Listing,RefreshSession
from backend.sessions import COOKIE_NAME,revoke_user_sessions,new_login_session

class AdminUsersPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 snapshot=fixture.SoldPostgreSQLTest.snapshot
 def setUp(self):
  fixture.SoldPostgreSQLTest.setUp(self);promote_existing_admin(self.database,self.buyer.email)
 def change(self,suspended=True,target=None,headers=None):return self.client.patch(f'/admin/users/{self.owner.id if target is None else target}/suspension',json={'suspended':suspended},headers=self.buyer_headers if headers is None else headers)
 def sessions(self,id):
  with self.database.session() as s:return [(r.id,r.revoked_at) for r in s.scalars(select(RefreshSession).where(RefreshSession.user_id==id).order_by(RefreshSession.id))]
 def test_list_minimal_stable_paging_and_strict_queries(self):
  result=self.client.get('/admin/users?limit=1',headers=self.buyer_headers);self.assertEqual(result.status_code,200);data=result.json();self.assertEqual((data['total'],data['count'],data['limit'],data['offset']),(2,1,1,0));self.assertEqual(data['items'][0]['id'],self.buyer.id);self.assertEqual(set(data['items'][0]),{'id','email','name','role','verified','suspended','created_at'})
  self.assertEqual(self.client.get('/admin/users?limit=1&offset=1',headers=self.buyer_headers).json()['items'][0]['id'],self.owner.id)
  self.assertEqual(self.client.get('/admin/users?offset=9223372036854775807',headers=self.buyer_headers).json()['items'],[])
  for query in ['limit=0','limit=51','offset=-1','offset=9223372036854775808','limit=01','limit=2&limit=3','sort=email','role=admin','offset=0&offset=0']:
   self.assertEqual(self.client.get('/admin/users?'+query,headers=self.buyer_headers).status_code,422)
  self.assertEqual(self.client.get('/admin/users',headers=self.headers).status_code,403);self.assertEqual(self.client.get('/admin/users').status_code,401)
 def test_suspend_all_sessions_hide_restore_listing_without_lifecycle_change(self):
  second_token=self.login(self.owner.email);raw=self.client.cookies.get(COOKIE_NAME);csrf=self.client.get('/auth/csrf').json()['csrf_token'];before=self.snapshot();admin_sessions=self.sessions(self.buyer.id)
  self.assertEqual(self.change().json(),{'id':self.owner.id,'suspended':True});revoked=self.sessions(self.owner.id);self.assertGreaterEqual(len(revoked),2);self.assertTrue(all(revoked_at for _,revoked_at in revoked));self.assertEqual(self.change().status_code,200);self.assertEqual(self.sessions(self.owner.id),revoked);self.assertEqual(self.sessions(self.buyer.id),admin_sessions);self.assertEqual(self.snapshot(),before)
  for token in [self.headers['Authorization'].split()[1],second_token]:self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
  self.assertEqual(self.client.post('/auth/refresh',headers={'Cookie':f'{COOKIE_NAME}={raw}','Origin':self.settings.frontend_origins[0],'X-CSRF-Token':csrf}).status_code,401)
  self.assertEqual(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}).status_code,401)
  self.assertEqual(self.client.get('/listings',headers=self.buyer_headers).json()['total'],0);self.assertEqual(self.client.get(f'/listings/{self.item.id}',headers=self.buyer_headers).status_code,404);self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.buyer_headers).status_code,404)
  self.assertEqual(self.change(False).status_code,200);self.assertEqual(self.sessions(self.owner.id),revoked);self.assertEqual(self.client.get('/auth/me',headers=self.headers).status_code,401);self.assertEqual(self.client.get('/listings',headers=self.buyer_headers).json()['total'],1);self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.buyer_headers).status_code,200);self.assertEqual(self.client.get(f'/listings/{self.item.id}',headers=self.buyer_headers).status_code,200);self.assertEqual(self.snapshot(),before);self.assertTrue(self.login(self.owner.email))
 def test_strict_boolean_target_policy_and_unverified_unsuspension(self):
  for body in [{},{'suspended':'true'},{'suspended':1},{'suspended':None},{'suspended':True,'role':'admin'},{'suspended':True,'user_id':self.owner.id}]:self.assertEqual(self.client.patch(f'/admin/users/{self.owner.id}/suspension',json=body,headers=self.buyer_headers).status_code,422)
  self.assertEqual(self.change(target=self.buyer.id).status_code,400);self.assertEqual(self.change(target=9223372036854775807).status_code,404)
  promote_existing_admin(self.database,self.owner.email);self.assertEqual(self.change().status_code,400)
  with self.database.session() as s:user=s.get(User,self.owner.id);user.role='student';user.verified=False;user.suspended=True
  self.assertEqual(self.change(False).status_code,200)
  with self.database.session() as s:user=s.get(User,self.owner.id);self.assertFalse(user.verified);self.assertFalse(user.suspended);self.assertEqual(user.role,'student')
  for id in [0,2**63]:self.assertEqual(self.change(target=id).status_code,422)
 def test_failed_commit_preserves_all_account_and_session_state(self):
  before=self.sessions(self.owner.id);original=Session.commit
  def fail(s):
   if s.get(User,self.owner.id).suspended:raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):
   result=self.change();self.assertEqual(result.status_code,500);self.assertNotIn('PRIVATE',result.text)
  self.assertEqual(self.sessions(self.owner.id),before)
  with self.database.session() as s:self.assertFalse(s.get(User,self.owner.id).suspended);self.assertFalse(s.get(User,self.buyer.id).suspended)
 def test_ascending_locks_allow_actor_demotion_while_waiting_for_lower_target(self):
  ready=Event();original=set_student_suspension
  def start(*a,**k):ready.set();return original(*a,**k)
  with ThreadPoolExecutor(max_workers=1) as pool:
   with self.database.session() as held:
    held.scalar(select(User).where(User.id==self.owner.id).with_for_update())
    with patch('backend.routers.admin.set_student_suspension',side_effect=start):
     future=pool.submit(self.change);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      s.execute(text("SET LOCAL lock_timeout = '1s'"));s.get(User,self.buyer.id).role='student';s.flush()
   self.assertEqual(future.result(timeout=5).status_code,403)
  with self.database.session() as s:self.assertFalse(s.get(User,self.owner.id).suspended)
 def test_concurrent_login_and_refresh_cannot_survive_suspension(self):
  from backend.sessions import rotate_refresh_session
  for operation in ['login','refresh']:
   self.change(False);self.login(self.owner.email);csrf=self.client.get('/auth/csrf').json()['csrf_token'];raw=self.client.cookies.get(COOKIE_NAME);ready,release=Event(),Event()
   original=new_login_session if operation=='login' else rotate_refresh_session
   def pause(*a,**k):ready.set();release.wait(5);return original(*a,**k)
   with patch('backend.routers.auth.'+('new_login_session' if operation=='login' else 'rotate_refresh_session'),side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     pending=pool.submit(self.client.post,'/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}) if operation=='login' else pool.submit(self.client.post,'/auth/refresh',headers={'Cookie':f'{COOKIE_NAME}={raw}','Origin':self.settings.frontend_origins[0],'X-CSRF-Token':csrf})
     self.assertTrue(ready.wait(5));self.assertEqual(self.change().status_code,200);release.set();self.assertEqual(pending.result(timeout=5).status_code,401)
   self.assertTrue(all(time for _,time in self.sessions(self.owner.id)))
 def test_revoked_admin_after_precheck_cannot_mutate(self):
  ready,release=Event(),Event()
  def pause(*a,**k):ready.set();release.wait(5);return set_student_suspension(*a,**k)
  with patch('backend.routers.admin.set_student_suspension',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    pending=pool.submit(self.change);self.assertTrue(ready.wait(5))
    with self.database.session() as s:revoke_user_sessions(s,self.buyer.id,self.now)
    release.set();self.assertEqual(pending.result(timeout=5).status_code,401)
  with self.database.session() as s:self.assertFalse(s.get(User,self.owner.id).suspended)
