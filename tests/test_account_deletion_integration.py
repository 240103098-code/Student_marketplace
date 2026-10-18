from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
import subprocess
import os
import unittest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.models import User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport
from backend.images import ImageStorage,ImageStorageError,canonical_image
from backend.account_deletion import delete_own_account
from backend.account_cleanup import cleanup_absent_account
from backend.sessions import revoke_user_sessions,COOKIE_NAME
from backend.admin import promote_existing_admin

class DeleteAccountPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 login=fixture.SoldPostgreSQLTest.login
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 def setUp(self):
  fixture.SoldPostgreSQLTest.setUp(self)
  self.avatar=ImageStorage(self.settings.upload_dir).write(canonical_image(fixture.picture()),self.owner.id)
  self.avatarfile=ImageStorage(self.settings.upload_dir).path(self.avatar,self.owner.id)
  self.photofile=ImageStorage(self.settings.upload_dir,'listings').path(self.photo.storage_path,self.item.id)
  with self.database.session() as s:
   user=s.get(User,self.owner.id);user.avatar_path=self.avatar;user.name='Private name';user.phone='+77001234567'
   s.add(EmailCode(user_id=user.id,purpose='registration',digest='private-digest',created_at=self.now,expires_at=self.now+timedelta(minutes=10)))
   self.other=Listing(owner_id=self.buyer.id,category_id=1,title='Other listing',description='An unrelated useful item.',price=10,condition='new',status='pending');s.add(self.other);s.flush()
   self.authored=ListingReport(listing_id=self.other.id,reporter_id=self.owner.id,reason='spam');s.add(self.authored)
   third=User(email='third@sdu.edu.kz',password_hash=self.owner.password_hash,verified=True);s.add(third);s.flush();self.thirdid=third.id
   self.keepreport=ListingReport(listing_id=self.other.id,reporter_id=third.id,reason='misleading_information');s.add(self.keepreport);s.flush()
  self.before=self.snapshot()
 def snapshot(self):
  with self.database.session() as s:
   return tuple(tuple((r.id,) for r in s.scalars(select(model).order_by(model.id))) for model in [User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport]),sorted((str(p),p.read_bytes()) for p in Path(self.temp.name).rglob('*') if p.is_file())
 def remove(self,password='TEST_SOLD_PASSWORD_123',headers=None):return self.client.request('DELETE','/users/me',headers=self.headers if headers is None else headers,json={'current_password':password})
 def assert_absent(self):
  with self.database.session() as s:
   self.assertIsNone(s.get(User,self.owner.id));self.assertIsNone(s.get(Listing,self.item.id));self.assertIsNone(s.get(ListingPhoto,self.photo.id));self.assertIsNone(s.get(ListingReport,self.authored.id));self.assertEqual(list(s.scalars(select(EmailCode).where(EmailCode.user_id==self.owner.id))),[]);self.assertEqual(list(s.scalars(select(RefreshSession).where(RefreshSession.user_id==self.owner.id))),[])
   self.assertIsNotNone(s.get(User,self.buyer.id));self.assertIsNotNone(s.get(User,self.thirdid));self.assertIsNotNone(s.get(Listing,self.other.id));self.assertIsNotNone(s.get(ListingReport,self.keepreport.id))
 def test_hard_cascades_isolation_private_access_and_cookie_clear(self):
  response=self.remove();self.assertEqual(response.status_code,200);self.assertEqual(response.json(),{'deleted':True,'cleanup_pending':False});self.assertIn('Max-Age=0',response.headers['set-cookie']);self.assert_absent();self.assertFalse(self.avatarfile.exists());self.assertFalse(self.photofile.exists());self.assertEqual(self.client.get('/auth/me',headers=self.headers).status_code,401);self.assertEqual(self.client.get(f'/listings/{self.item.id}',headers=self.buyer_headers).status_code,404);self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.buyer_headers).status_code,404);self.assertEqual(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}).status_code,401)
 def test_wrong_and_malformed_passwords_change_nothing(self):
  self.assertEqual(self.remove('WRONG_PASSWORD_123').status_code,400)
  for body in [{},{'current_password':None},{'current_password':True},{'current_password':'x'*11},{'current_password':'x'*129},{'current_password':'TEST_SOLD_PASSWORD_123','user_id':self.buyer.id}]:
   response=self.client.request('DELETE','/users/me',headers=self.headers,json=body);self.assertEqual(response.status_code,422);self.assertNotIn('TEST_SOLD_PASSWORD_123',response.text)
  for raw in ['{"current_password":"TEST_SOLD_PASSWORD_123","current_password":"TEST_SOLD_PASSWORD_123"}','null']:
   self.assertEqual(self.client.request('DELETE','/users/me',headers=self.headers,content=raw).status_code,422)
  self.assertEqual(self.snapshot(),self.before)
 def test_admin_self_deletion_has_no_last_admin_exception(self):
  promote_existing_admin(self.database,self.owner.email);self.assertEqual(self.remove().status_code,200);self.assert_absent()
 def test_commit_failure_preserves_rows_and_files(self):
  original=Session.commit
  def fail(s):
   if s.get(User,self.owner.id) is None:raise SQLAlchemyError('PRIVATE_DRIVER')
   return original(s)
  with patch.object(Session,'commit',fail):
   response=self.remove();self.assertEqual(response.status_code,500);self.assertNotIn('PRIVATE',response.text)
  self.assertEqual(self.snapshot(),self.before)
 def test_missing_files_and_cleanup_failure_scoped_recovery(self):
  self.avatarfile.unlink();marker=self.photofile.parent/'keep.txt';marker.write_text('keep')
  with self.assertRaises(ValueError):cleanup_absent_account(self.database,self.settings,self.owner.id,self.owner.id,[self.item.id],[self.item.id])
  with patch.object(ImageStorage,'delete',side_effect=ImageStorageError('PRIVATE_PATH')):
   response=self.remove();self.assertEqual(response.json(),{'deleted':True,'cleanup_pending':True});self.assertNotIn('PRIVATE_PATH',response.text)
  self.assert_absent();self.assertTrue(self.photofile.exists())
  for uid,confirmed,ids,confirmids in [(self.owner.id,self.owner.id+1,[],[]),(self.owner.id,self.owner.id,[self.item.id],[]),(self.owner.id,self.owner.id,[self.other.id],[self.other.id])]:
   with self.assertRaises(ValueError):cleanup_absent_account(self.database,self.settings,uid,confirmed,ids,confirmids)
  self.assertTrue(self.photofile.exists());self.assertFalse(cleanup_absent_account(self.database,self.settings,self.owner.id,self.owner.id,[self.item.id],[self.item.id]));self.assertFalse(self.photofile.exists());self.assertTrue(marker.exists())
 def test_normal_missing_files_are_success(self):
  self.avatarfile.unlink();self.photofile.unlink();self.assertEqual(self.remove().json(),{'deleted':True,'cleanup_pending':False})
 def test_unsafe_generated_path_prevents_commit_and_outside_removal(self):
  with self.database.session() as s:s.get(User,self.owner.id).avatar_path='../outside.png'
  with self.database.session() as s:before=s.get(User,self.owner.id).avatar_path
  self.assertEqual(self.remove().status_code,500)
  with self.database.session() as s:self.assertEqual(s.get(User,self.owner.id).avatar_path,before)
  self.assertTrue(self.avatarfile.exists());self.assertTrue(self.photofile.exists())
 def test_real_junction_is_rejected_before_deletion_or_recovery(self):
  outside=Path(self.temp.name)/'outside';outside.mkdir();target=outside/self.avatarfile.name;target.write_bytes(b'keep')
  self.avatarfile.unlink();self.avatarfile.parent.rmdir();junction=self.avatarfile.parent
  if os.name=='nt':
   result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],capture_output=True)
   self.assertEqual(result.returncode,0)
  else:junction.symlink_to(outside,target_is_directory=True)
  try:
   self.assertEqual(self.remove().status_code,500);self.assertEqual(target.read_bytes(),b'keep')
   with self.database.session() as s:s.get(User,self.owner.id).avatar_path=None
   self.assertEqual(self.remove().status_code,200)
   with self.assertRaises(ImageStorageError):cleanup_absent_account(self.database,self.settings,self.owner.id,self.owner.id)
   self.assertEqual(target.read_bytes(),b'keep')
  finally:
   if junction.is_symlink():junction.unlink()
   else:junction.rmdir()
 def test_stale_revoked_ineligible_or_changed_password_guard(self):
  for change in ['verified','suspended','password','revoke']:
   ready,release=Event(),Event()
   def pause(*a,**k):ready.set();release.wait(5);return delete_own_account(*a,**k)
   with patch('backend.routers.users.delete_own_account',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.remove);self.assertTrue(ready.wait(5))
     with self.database.session() as s:
      user=s.get(User,self.owner.id)
      if change=='verified':user.verified=False
      elif change=='suspended':user.suspended=True
      elif change=='password':user.password_hash=fixture.PasswordHasher().hash('NEW_PASSWORD_123456')
      else:revoke_user_sessions(s,user.id,self.now)
     release.set();self.assertEqual(future.result(timeout=5).status_code,400 if change=='password' else 401)
   with self.database.session() as s:
    user=s.get(User,self.owner.id);self.assertIsNotNone(user);user.verified=True;user.suspended=False;user.password_hash=self.owner.password_hash
   self.headers={'Authorization':'Bearer '+self.login(self.owner.email)}
 def test_racing_login_refresh_listing_and_admin_cannot_survive_deletion(self):
  promote_existing_admin(self.database,self.buyer.email)
  grant=self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'})
  cookie=grant.cookies.get(COOKIE_NAME)
  csrf=self.client.get('/auth/csrf',headers={'Cookie':f'{COOKIE_NAME}={cookie}','Origin':'http://localhost:5173'}).json()['csrf_token']
  # Hold the account lock during deletion, while all competing services start waiting.
  ready,release=Event(),Event();original=fixture.PasswordHasher.verify
  def pause(hasher,hash,password):
   if hash==self.owner.password_hash:ready.set();release.wait(5)
   return original(hasher,hash,password)
  with patch('backend.account_deletion.PasswordHasher.verify',pause):
   with ThreadPoolExecutor(max_workers=5) as pool:
    deletion=pool.submit(self.remove);self.assertTrue(ready.wait(5))
    login=pool.submit(self.client.post,'/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'})
    edit=pool.submit(self.client.patch,f'/listings/{self.item.id}',headers=self.headers,json={'price':'15'})
    suspend=pool.submit(self.client.patch,f'/admin/users/{self.owner.id}/suspension',headers=self.buyer_headers,json={'suspended':True})
    refresh=pool.submit(self.client.post,'/auth/refresh',headers={'Cookie':f'{COOKIE_NAME}={cookie}','Origin':'http://localhost:5173','X-CSRF-Token':csrf})
    release.set();self.assertEqual(deletion.result(timeout=10).status_code,200)
    self.assertEqual(refresh.result(timeout=10).status_code,401);self.assertEqual(login.result(timeout=10).status_code,401);self.assertEqual(edit.result(timeout=10).status_code,401);self.assertEqual(suspend.result(timeout=10).status_code,404)
  self.assert_absent()


 def test_password_spaces_are_not_trimmed(self):
  password=' '+('x'*126)+' '
  with self.database.session() as s:s.get(User,self.owner.id).password_hash=fixture.PasswordHasher().hash(password)
  self.assertEqual(self.remove(password.strip()).status_code,400)
  self.assertEqual(self.remove(password).status_code,200)
  self.assert_absent()
