from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import patch
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.models import Listing,ListingReport,User
from backend.listings import report_listing
from backend.sessions import revoke_user_sessions

class ReportPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 def setUp(self):
  fixture.SoldPostgreSQLTest.setUp(self)
  with self.database.session() as s:s.execute(delete(ListingReport))
 def report(self,reason='spam',headers=None):return self.client.post(f'/listings/{self.item.id}/reports',json={'reason':reason},headers=self.buyer_headers if headers is None else headers)
 def rows(self):
  with self.database.session() as s:return list(s.scalars(select(ListingReport)))
 def test_valid_reasons_server_identity_time_and_privacy(self):
  for reason in ['spam','prohibited_items','misleading_information']:
   with self.database.session() as s:s.execute(delete(ListingReport))
   result=self.report(reason);self.assertEqual(result.status_code,202);self.assertEqual(result.json(),{'accepted':True});row=self.rows()[0];self.assertGreater(row.id,0);self.assertEqual((row.reporter_id,row.listing_id,row.reason,row.created_at,row.reviewed_at),(self.buyer.id,self.item.id,reason,self.now,None))
  self.assertEqual(self.client.get(f'/listings/{self.item.id}',headers=self.buyer_headers).status_code,200)
 def test_repeats_concurrent_preserve_original_and_other_reporter_isolated(self):
  with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda _:self.report(),range(3)))
  self.assertEqual([r.status_code for r in results],[202]*3);first=self.rows()[0];self.assertEqual(len(self.rows()),1);self.assertEqual(self.report('prohibited_items').status_code,202);self.assertEqual([(r.id,r.reason,r.created_at) for r in self.rows()],[(first.id,'spam',first.created_at)])
  with self.database.session() as s:
   other=User(email='reporter@sdu.edu.kz',password_hash=self.buyer.password_hash,verified=True);s.add(other);s.flush();email=other.email
  headers={'Authorization':'Bearer '+self.login(email)};self.assertEqual(self.report('misleading_information',headers).status_code,202);self.assertEqual(len(self.rows()),2)
 def test_strict_payload_and_bounded_ids(self):
  for body in [{},{'reason':None},{'reason':True},{'reason':1},{'reason':['spam']},{'reason':'Spam'},{'reason':'other'},{'reason':'spam','reporter_id':self.owner.id},{'reason':'spam','reviewed_at':None},{'reason':'spam','comment':'text'},{'reason':'spam','evidence':'text'}]:
   result=self.client.post(f'/listings/{self.item.id}/reports',json=body,headers=self.buyer_headers);self.assertEqual(result.status_code,422);self.assertEqual(result.json(),{'detail':'Invalid listing-report request.'})
  self.assertEqual(self.client.post(f'/listings/{self.item.id}/reports?reporter_id=1',json={'reason':'spam'},headers=self.buyer_headers).status_code,422)
  for id in [0,2**63]:self.assertEqual(self.client.post(f'/listings/{id}/reports',json={'reason':'spam'},headers=self.buyer_headers).status_code,422)
  self.assertEqual(self.rows(),[])
 def test_visibility_self_and_viewer_eligibility(self):
  self.assertEqual(self.report(headers=self.headers).status_code,400);self.assertEqual(self.report(headers={}).status_code,401)
  for state in ['pending','sold','rejected','removed']:
   with self.database.session() as s:row=s.get(Listing,self.item.id);row.status=state;row.published_at=self.now if state=='sold' else None;row.rejection_reason='Private' if state=='rejected' else None
   self.assertEqual(self.report().status_code,404)
  with self.database.session() as s:row=s.get(Listing,self.item.id);row.status='active';row.published_at=self.now;s.get(User,self.owner.id).suspended=True
  self.assertEqual(self.report().status_code,404)
  with self.database.session() as s:s.get(User,self.owner.id).suspended=False;s.get(User,self.owner.id).verified=False
  self.assertEqual(self.report().status_code,404)
  with self.database.session() as s:s.get(User,self.owner.id).verified=True;s.get(User,self.buyer.id).suspended=True
  self.assertEqual(self.report().status_code,401);self.assertEqual(self.rows(),[])
 def test_stale_state_or_revocation_before_mutation_writes_nothing(self):
  for change in ['state','revoke']:
   ready,release=Event(),Event()
   def pause(*args,**kwargs):ready.set();release.wait(5);return report_listing(*args,**kwargs)
   with patch('backend.routers.listings.report_listing',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.report);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      if change=='state':s.get(Listing,self.item.id).status='sold'
      else:revoke_user_sessions(s,self.buyer.id,self.now)
     release.set();self.assertEqual(future.result(timeout=5).status_code,404 if change=='state' else 401)
   self.assertEqual(self.rows(),[])
   with self.database.session() as s:s.get(Listing,self.item.id).status='active'
 def test_commit_failure_preserves_listing_and_no_partial_report(self):
  original=Session.commit
  def fail(s):
   if s.scalar(select(ListingReport.id)) is not None:raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):
   result=self.report();self.assertEqual(result.status_code,500);self.assertNotIn('PRIVATE',result.text)
  self.assertEqual(self.rows(),[])
  with self.database.session() as s:self.assertEqual(s.get(Listing,self.item.id).status,'active')
