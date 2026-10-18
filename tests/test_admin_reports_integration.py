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
from backend.admin_reports import mark_admin_report_reviewed
from backend.models import User,Listing,ListingReport
from backend.sessions import revoke_user_sessions

class AdminReportsPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 snapshot=fixture.SoldPostgreSQLTest.snapshot
 def setUp(self):
  fixture.SoldPostgreSQLTest.setUp(self);promote_existing_admin(self.database,self.buyer.email)
  with self.database.session() as s:report=s.scalar(select(ListingReport));report.created_at=self.now;self.report_id=report.id
 def mark(self,headers=None):return self.client.post(f'/admin/reports/{self.report_id}/review',headers=self.buyer_headers if headers is None else headers)
 def queue(self,query=''):return self.client.get('/admin/reports'+query,headers=self.buyer_headers)
 def row(self,id=None):
  with self.database.session() as s:return s.get(ListingReport,id or self.report_id)
 def extra_reporter(self):
  with self.database.session() as s:
   other=User(email='reporter@sdu.edu.kz',password_hash=self.owner.password_hash,verified=True);s.add(other);s.flush();return other.id
 def test_filters_tie_order_counts_bounds_and_minimal_privacy(self):
  other=self.extra_reporter()
  with self.database.session() as s:
   report=ListingReport(listing_id=self.item.id,reporter_id=other,reason='prohibited_items',created_at=self.now,reviewed_at=self.now);s.add(report);s.flush();new_id=report.id
  default=self.queue().json();self.assertEqual((default['state'],default['total']),("unreviewed",1));self.assertEqual(default['items'][0]['id'],self.report_id)
  first=self.queue('?state=all&limit=1').json();self.assertEqual(first['total'],2);self.assertEqual(first['items'][0]['id'],new_id);self.assertEqual(self.queue('?state=all&limit=1&offset=1').json()['items'][0]['id'],self.report_id);self.assertEqual(self.queue('?state=reviewed').json()['items'][0]['id'],new_id);self.assertEqual(self.queue('?offset=9223372036854775807').json()['items'],[])
  row=first['items'][0];self.assertEqual(set(row),{'id','reason','created_at','reviewed_at','listing'});self.assertEqual(row['listing'],{'id':self.item.id,'title':self.item.title,'status':'active','url':f'/admin/listings/{self.item.id}'})
  for word in ['reporter','email','phone','token','storage_path','password']:self.assertNotIn(word,self.queue('?state=all').text)
  for query in ['state=','state=closed','state=all&state=reviewed','limit=0','limit=51','offset=-1','offset=9223372036854775808','sort=id','reporter_id=1','limit=1&limit=2']:
   self.assertEqual(self.queue('?'+query).status_code,422)
 def test_concurrent_review_is_idempotent_and_preserves_original_fields(self):
  other=self.extra_reporter();promote_existing_admin(self.database,'reporter@sdu.edu.kz');headers={'Authorization':'Bearer '+self.login('reporter@sdu.edu.kz')};before=self.snapshot();row_before=self.row()
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(self.mark,[self.buyer_headers,headers]))
  self.assertEqual([r.status_code for r in results],[200,200]);self.assertEqual(results[0].json(),results[1].json());self.assertEqual(set(results[0].json()),{'id','reviewed_at'});reviewed=self.row().reviewed_at;self.assertEqual(reviewed,self.now)
  self.client.app.state.clock=lambda:self.now+timedelta(seconds=20);self.assertEqual(self.mark().status_code,200);self.assertEqual(self.row().reviewed_at,reviewed);self.assertEqual((self.row().reason,self.row().created_at),(row_before.reason,row_before.created_at));self.assertEqual(self.snapshot(),before);self.assertEqual(self.queue('?state=unreviewed').json()['total'],0)
 def test_guards_strict_empty_action_and_rollback(self):
  self.assertEqual(self.mark({}).status_code,401);self.assertEqual(self.mark(self.headers).status_code,403);self.assertEqual(self.client.get('/admin/reports',headers=self.headers).status_code,403);self.assertEqual(self.client.get('/admin/reports').status_code,401)
  with self.database.session() as s:s.get(User,self.buyer.id).suspended=True
  self.assertEqual(self.mark().status_code,401)
  with self.database.session() as s:s.get(User,self.buyer.id).suspended=False
  for body in [{'reviewed_at':'now'},{'reviewer_id':self.owner.id},{'status':'reviewed'},[]]:self.assertEqual(self.client.post(f'/admin/reports/{self.report_id}/review',json=body,headers=self.buyer_headers).status_code,422)
  self.assertEqual(self.client.post(f'/admin/reports/{self.report_id}/review',content='null',headers=self.buyer_headers).status_code,422)
  for id in [0,2**63]:self.assertEqual(self.client.post(f'/admin/reports/{id}/review',headers=self.buyer_headers).status_code,422)
  original=Session.commit
  def fail(s):
   if s.get(ListingReport,self.report_id).reviewed_at is not None:raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):result=self.mark();self.assertEqual(result.status_code,500);self.assertNotIn('PRIVATE',result.text)
  self.assertIsNone(self.row().reviewed_at)
 def test_stale_admin_role_or_session_prevents_review(self):
  for change in ['role','revoke']:
   ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return mark_admin_report_reviewed(*a,**k)
   with patch('backend.routers.admin.mark_admin_report_reviewed',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.mark);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      if change=='role':s.get(User,self.buyer.id).role='student'
      else:revoke_user_sessions(s,self.buyer.id,self.now)
     release.set();self.assertEqual(future.result(timeout=5).status_code,403 if change=='role' else 401)
   self.assertIsNone(self.row().reviewed_at)
   with self.database.session() as s:s.get(User,self.buyer.id).role='admin'
 def test_removed_listing_reports_stay_unreviewed_until_explicit_action(self):
  ready,release=Event(),Event()
  def pause(*a,**k):ready.set();release.wait(5);return mark_admin_report_reviewed(*a,**k)
  with patch('backend.routers.admin.mark_admin_report_reviewed',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.mark);self.assertTrue(ready.wait(5));self.assertEqual(self.client.post(f'/admin/listings/{self.item.id}/remove',headers=self.buyer_headers).status_code,200);self.assertIsNone(self.row().reviewed_at);release.set();self.assertEqual(future.result(timeout=5).status_code,200)
  self.assertEqual(self.queue('?state=reviewed').json()['items'][0]['listing']['status'],'removed');self.assertEqual(self.client.get(f'/admin/listings/{self.item.id}',headers=self.buyer_headers).status_code,200)
 def test_concurrent_new_report_is_not_reviewed_and_deletion_cascades(self):
  other=self.extra_reporter();student={'Authorization':'Bearer '+self.login('reporter@sdu.edu.kz')};ready,release=Event(),Event()
  def pause(*a,**k):ready.set();release.wait(5);return mark_admin_report_reviewed(*a,**k)
  with patch('backend.routers.admin.mark_admin_report_reviewed',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.mark);self.assertTrue(ready.wait(5));self.assertEqual(self.client.post(f'/listings/{self.item.id}/reports',json={'reason':'misleading_information'},headers=student).status_code,202);release.set();self.assertEqual(future.result(timeout=5).status_code,200)
  remaining=self.queue().json();self.assertEqual(remaining['total'],1);self.assertEqual(remaining['items'][0]['reason'],'misleading_information');self.assertIsNone(remaining['items'][0]['reviewed_at'])
  with self.database.session() as s:s.delete(s.get(User,self.owner.id))
  self.assertEqual(self.queue('?state=all').json()['items'],[]);self.assertEqual(self.mark().status_code,404)
 def test_racing_seller_hard_delete_returns_safe_missing_without_dangling_report(self):
  ready,release=Event(),Event()
  def pause(*a,**k):ready.set();release.wait(5);return mark_admin_report_reviewed(*a,**k)
  with patch('backend.routers.admin.mark_admin_report_reviewed',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.mark);self.assertTrue(ready.wait(5));self.assertEqual(self.client.delete(f'/listings/{self.item.id}',headers=self.headers).status_code,200);release.set();self.assertEqual(future.result(timeout=5).status_code,404)
  self.assertEqual(self.queue('?state=all').json()['total'],0)
