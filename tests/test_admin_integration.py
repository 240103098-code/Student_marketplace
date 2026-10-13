from contextlib import redirect_stdout
from io import StringIO
import importlib
import unittest
from unittest.mock import patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.admin import promote_existing_admin,main,AdminProvisioningError,locked_admin_user
from backend.models import User
from backend.sessions import revoke_user_sessions

class AdminPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def test_cli_success_normalization_idempotence_isolation_and_cleanup(self):
  before=(self.owner.password_hash,self.owner.email,self.owner.name,self.owner.verified)
  for _ in range(2):
   with patch('backend.admin.load_settings',return_value=self.settings),patch('backend.admin.Database',return_value=self.database),patch.object(self.database,'dispose',wraps=self.database.dispose) as dispose,redirect_stdout(StringIO()) as output:
    self.assertEqual(main(['--email',' SELLER@SDU.EDU.KZ ']),0);dispose.assert_called_once();self.assertEqual(output.getvalue(),'Admin provisioning completed.\n')
  with self.database.session() as s:
   user=s.get(User,self.owner.id);self.assertEqual((user.password_hash,user.email,user.name,user.verified),before);self.assertEqual(user.role,'admin');self.assertEqual(s.get(User,self.buyer.id).role,'student')
  self.assertEqual(self.client.get('/auth/me',headers=self.headers).json()['is_admin'],True);self.assertEqual(self.client.get('/admin/me',headers=self.headers).json(),{'id':self.owner.id,'is_admin':True})
 def test_missing_invalid_unverified_suspended_refusal(self):
  for email in ['absent@sdu.edu.kz','bad@example.com','bad@@sdu.edu.kz','admin@sub.sdu.edu.kz']:
   with self.assertRaises(AdminProvisioningError):promote_existing_admin(self.database,email)
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,value)
   with self.assertRaises(AdminProvisioningError):promote_existing_admin(self.database,self.owner.email)
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,not value);self.assertEqual(s.get(User,self.owner.id).role,'student')
 def test_failed_commit_rolls_back_and_cli_error_is_sanitized(self):
  with patch.object(Session,'commit',side_effect=SQLAlchemyError('SECRET_DATABASE')),self.assertRaises(SQLAlchemyError):promote_existing_admin(self.database,self.owner.email)
  with self.database.session() as s:self.assertEqual(s.get(User,self.owner.id).role,'student')
  with patch('backend.admin.load_settings',return_value=self.settings),patch('backend.admin.Database',return_value=self.database),patch('backend.admin.promote_existing_admin',side_effect=SQLAlchemyError('SECRET_DATABASE')),redirect_stdout(StringIO()) as output:
   self.assertEqual(main(['--email',self.owner.email]),1);self.assertNotIn('SECRET',output.getvalue());self.assertNotIn(self.owner.email,output.getvalue())
 def test_current_guard_student_admin_demotion_and_revocation(self):
  self.assertEqual(self.client.get('/admin/me').status_code,401);self.assertEqual(self.client.get('/admin/me',headers=self.buyer_headers).status_code,403);self.assertEqual(self.client.get('/auth/me',headers=self.buyer_headers).json()['is_admin'],False)
  promote_existing_admin(self.database,self.buyer.email);self.assertEqual(self.client.get('/admin/me',headers=self.buyer_headers).status_code,200)
  with self.database.session() as s:s.get(User,self.buyer.id).role='student'
  self.assertEqual(self.client.get('/admin/me',headers=self.buyer_headers).status_code,403);self.assertEqual(self.client.get('/auth/me',headers=self.buyer_headers).status_code,200)
  promote_existing_admin(self.database,self.buyer.email)
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,value)
   self.assertEqual(self.client.get('/admin/me',headers=self.buyer_headers).status_code,401)
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,not value)
  with self.database.session() as s:revoke_user_sessions(s,self.buyer.id,self.now)
  self.assertEqual(self.client.get('/admin/me',headers=self.buyer_headers).status_code,401)
 def test_stale_role_or_eligibility_is_rechecked(self):
  from threading import Event
  from concurrent.futures import ThreadPoolExecutor
  promote_existing_admin(self.database,self.buyer.email)
  for field,value in [('role','student'),('suspended',True)]:
   ready,release=Event(),Event()
   def pause(*args,**kwargs):ready.set();release.wait(5);return locked_admin_user(*args,**kwargs)
   with patch('backend.admin.locked_admin_user',side_effect=pause):
    with ThreadPoolExecutor(max_workers=1) as pool:
     future=pool.submit(self.client.get,'/admin/me',headers=self.buyer_headers);self.assertTrue(ready.wait(5))
     with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,value)
     release.set();self.assertEqual(future.result(timeout=5).status_code,403 if field=='role' else 401)
   with self.database.session() as s:s.get(User,self.buyer.id).role='admin'

class AdminImportTest(unittest.TestCase):
 def test_import_never_loads_settings_or_database(self):
  import subprocess,sys
  script="from unittest.mock import patch\nwith patch('backend.config.load_settings',side_effect=AssertionError('No settings')),patch('backend.database.Database',side_effect=AssertionError('No database')):\n import backend.admin"
  result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
