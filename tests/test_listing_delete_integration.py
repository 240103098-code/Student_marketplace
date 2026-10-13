import unittest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.models import Listing,ListingPhoto,ListingReport,User
from backend.images import ImageStorage,ImageStorageError
from backend.listing_cleanup import cleanup_absent_listing

class DeleteListingPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def remove(self,headers=None):return self.client.delete(f'/listings/{self.item.id}',headers=self.headers if headers is None else headers)
 def file(self):return ImageStorage(self.settings.upload_dir,'listings').path(self.photo.storage_path,self.item.id)
 def present(self):
  with self.database.session() as s:
   self.assertIsNotNone(s.get(Listing,self.item.id));self.assertIsNotNone(s.get(ListingPhoto,self.photo.id));self.assertEqual(len(list(s.scalars(select(ListingReport)))),1)
  self.assertTrue(self.file().exists())
 def test_all_states_cascade_metadata_and_files_preserve_accounts(self):
  for state in ['pending','active','sold','rejected','removed']:
   with self.subTest(state=state):
    if state!='pending':self.tearDown();self.setUp()
    with self.database.session() as s:
     row=s.get(Listing,self.item.id);row.status=state;row.published_at=self.now if state in ['active','sold'] else None;row.rejection_reason='Rejected.' if state=='rejected' else None
    with self.database.session() as s:
     other=Listing(owner_id=self.buyer.id,category_id=1,title='Other listing',description='Another useful description.',price=self.item.price,condition='used',status='pending');s.add(other);s.flush();other_report=ListingReport(listing_id=other.id,reporter_id=self.owner.id,reason='spam');s.add(other_report);s.flush();other_id=other.id;report_id=other_report.id
    avatar=ImageStorage(self.settings.upload_dir).write(fixture.canonical_image(fixture.picture()),self.owner.id)
    path=self.file();result=self.remove();self.assertEqual(result.status_code,200);self.assertEqual(result.json(),{'id':self.item.id,'deleted':True,'cleanup_pending':False});self.assertFalse(path.exists())
    with self.database.session() as s:
     self.assertIsNone(s.get(Listing,self.item.id));self.assertIsNone(s.get(ListingPhoto,self.photo.id));self.assertIsNotNone(s.get(Listing,other_id));self.assertIsNotNone(s.get(ListingReport,report_id));self.assertEqual(list(s.scalars(select(ListingReport).where(ListingReport.listing_id==self.item.id))),[]);self.assertIsNotNone(s.get(User,self.owner.id));self.assertIsNotNone(s.get(User,self.buyer.id))
    self.assertEqual(self.client.get('/listings/mine',headers=self.headers).json()['total'],0);self.assertTrue(ImageStorage(self.settings.upload_dir).path(avatar,self.owner.id).exists());self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.headers).status_code,404)
 def test_owner_missing_validation_and_ineligible(self):
  self.assertEqual(self.remove(self.buyer_headers).status_code,404);self.present()
  for body in ['null','[]','{"owner_id":1}']:
   self.assertEqual(self.client.request('DELETE',f'/listings/{self.item.id}',content=body,headers=self.headers).status_code,422)
  for id in [0,2**63]:self.assertEqual(self.client.delete(f'/listings/{id}',headers=self.headers).status_code,422)
  self.assertEqual(self.remove().status_code,200);self.assertEqual(self.remove().status_code,404)
 def test_failed_commit_preserves_database_and_files(self):
  original=Session.commit
  def fail(s):
   if s.get(Listing,self.item.id) is None:raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):self.assertEqual(self.remove().status_code,500)
  self.present()
 def test_missing_file_is_success(self):
  self.file().unlink();self.assertEqual(self.remove().json()['cleanup_pending'],False)
 def test_cleanup_failure_and_confined_operator_recovery(self):
  path=self.file();marker=path.parent/'keep.txt';marker.write_text('unrelated');outside=self.settings.upload_dir/'keep.png';outside.write_bytes(b'private')
  with self.assertRaises(ValueError):cleanup_absent_listing(self.database,self.settings,self.item.id,self.item.id)
  with patch.object(ImageStorage,'delete',side_effect=ImageStorageError('PRIVATE_PATH')):
   result=self.remove();self.assertEqual(result.status_code,200);self.assertTrue(result.json()['cleanup_pending'])
  self.assertTrue(path.exists())
  with self.assertRaises(ValueError):cleanup_absent_listing(self.database,self.settings,self.item.id,self.item.id+1)
  self.assertFalse(cleanup_absent_listing(self.database,self.settings,self.item.id,self.item.id));self.assertFalse(path.exists());self.assertTrue(marker.exists());self.assertEqual(outside.read_bytes(),b'private')
 def test_path_validation_failure_precedes_database_commit(self):
  with patch.object(ImageStorage,'path',side_effect=ImageStorageError('PRIVATE_PATH')):self.assertEqual(self.remove().status_code,500)
  self.present()
 def test_concurrent_delete_only_one_confirmed_and_suspended_denied(self):
  from concurrent.futures import ThreadPoolExecutor
  with self.database.session() as s:s.get(User,self.owner.id).suspended=True
  self.assertEqual(self.remove().status_code,401);self.present()
  with self.database.session() as s:s.get(User,self.owner.id).suspended=False
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.remove(),range(2)))
  self.assertEqual(sorted(r.status_code for r in results),[200,404])
 def test_real_junction_escape_blocked_for_delete_and_recovery(self):
  import os,subprocess
  folder=self.file().parent;self.file().unlink();folder.rmdir();outside=self.settings.upload_dir/'outside';outside.mkdir();marker=outside/('f'*32+'.png');marker.write_bytes(b'preserve')
  try:os.symlink(outside,folder,target_is_directory=True)
  except OSError:
   escaped=str(folder).replace("'","''");target=str(outside).replace("'","''")
   subprocess.run(['powershell','-NoProfile','-Command',f"New-Item -ItemType Junction -Path '{escaped}' -Target '{target}' | Out-Null"],check=True,capture_output=True)
  try:
   self.assertEqual(self.remove().status_code,500)
   with self.database.session() as s:self.assertIsNotNone(s.get(Listing,self.item.id));s.delete(s.get(Listing,self.item.id))
   with self.assertRaises(ImageStorageError):cleanup_absent_listing(self.database,self.settings,self.item.id,self.item.id)
   self.assertEqual(marker.read_bytes(),b'preserve')
  finally:
   if folder.is_symlink():folder.unlink()
   else:folder.rmdir()
 def test_stale_guard_revocation_preserves_record_and_file(self):
  from threading import Event
  from concurrent.futures import ThreadPoolExecutor
  from backend.listings import delete_own_listing
  from backend.sessions import revoke_user_sessions
  ready,release=Event(),Event()
  def pause(*args,**kwargs):ready.set();release.wait(5);return delete_own_listing(*args,**kwargs)
  with patch('backend.routers.listings.delete_own_listing',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.remove);self.assertTrue(ready.wait(5))
    with self.database.session() as s:revoke_user_sessions(s,self.owner.id,self.now)
    release.set();self.assertEqual(future.result(timeout=5).status_code,401)
  self.present()
