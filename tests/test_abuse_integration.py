from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import Mock
import unittest
from sqlalchemy import select
import test_sold_integration as fixture
from backend.models import User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport
from backend.abuse import Limiter
from backend.images import ImageStorage

class AbusePostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def snapshot(self):
  with self.database.session() as s:return tuple(tuple(tuple(getattr(r,column.name) for column in model.__table__.columns) for r in s.scalars(select(model).order_by(model.id))) for model in [User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport])
 def rejected(self,response):
  self.assertEqual(response.status_code,429);self.assertGreater(int(response.headers['Retry-After']),0);self.assertEqual(response.headers['Cache-Control'],'private, no-store');self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff');self.assertNotIn('seller@sdu.edu.kz',response.text)
 def test_email_request_limit_shared_across_routes_normalization_unknown_and_cooldown(self):
  sender=Mock();self.client.app.state.email_sender=sender
  # The same pre-lookup email quota applies to unknown, unverified and eligible accounts.
  for email in ['unknown@sdu.edu.kz',self.owner.email]:
   self.client.app.state.limiter=Limiter(lambda:self.now)
   for path in ['/auth/resend-verification','/auth/forgot-password','/auth/resend-verification','/auth/forgot-password','/auth/resend-verification']:
    self.assertEqual(self.client.post(path,json={'email':' '+email.upper()+' '}).status_code,202)
   before=self.snapshot();sent=sender.send_code.call_count
   self.rejected(self.client.post('/auth/register',json={'email':email,'password':'TEST_SECURITY_PASSWORD_123'}));self.assertEqual(self.snapshot(),before);self.assertEqual(sender.send_code.call_count,sent)
  self.client.app.state.limiter=Limiter(lambda:self.now)
  self.assertEqual(self.client.post('/auth/register',json={'email':'new@sdu.edu.kz','password':'TEST_SECURITY_PASSWORD_123'}).status_code,201)
  sent=sender.send_code.call_count
  self.assertEqual(self.client.post('/auth/resend-verification',json={'email':'new@sdu.edu.kz'}).status_code,202);self.assertEqual(sender.send_code.call_count,sent)
 def test_registration_and_recovery_ip_boundaries_spoof_and_no_side_effect(self):
  sender=Mock();self.client.app.state.email_sender=sender
  for n in range(10):self.assertEqual(self.client.post('/auth/register',headers={'X-Forwarded-For':str(n)},json={'email':f'reg{n}@sdu.edu.kz','password':'TEST_SECURITY_PASSWORD_123'}).status_code,201)
  before=self.snapshot();self.rejected(self.client.post('/auth/register',headers={'X-Forwarded-For':'192.0.2.99'},json={'email':'next@sdu.edu.kz','password':'TEST_SECURITY_PASSWORD_123'}));self.assertEqual(self.snapshot(),before);self.assertEqual(sender.send_code.call_count,10)
  for n in range(10):self.assertEqual(self.client.post('/auth/forgot-password',json={'email':f'unknown{n}@sdu.edu.kz'}).status_code,202)
  before=self.snapshot();self.rejected(self.client.post('/auth/forgot-password',json={'email':'nextunknown@sdu.edu.kz'}));self.assertEqual(self.snapshot(),before);self.assertEqual(sender.send_code.call_count,10)
 def test_ten_failed_logins_pair_concurrency_and_exact_reset(self):
  def failed(_):return self.client.post('/auth/login',headers={'X-Forwarded-For':'spoof'},json={'email':' SELLER@SDU.EDU.KZ ','password':'WRONG_SECURITY_PASSWORD_123'})
  before=self.snapshot()
  with ThreadPoolExecutor(max_workers=15) as pool:responses=list(pool.map(failed,range(15)))
  self.assertEqual(sum(r.status_code==401 for r in responses),10);self.assertEqual(sum(r.status_code==429 for r in responses),5);self.assertEqual(self.snapshot(),before)
  self.rejected(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}))
  self.assertEqual(self.client.post('/auth/login',json={'email':self.buyer.email,'password':'TEST_SOLD_PASSWORD_123'}).status_code,200)
  self.now+=timedelta(minutes=15)
  self.assertEqual(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}).status_code,200)
 def test_successful_logins_do_not_consume_failed_quota_and_capacity_fails_closed(self):
  for _ in range(11):self.assertEqual(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}).status_code,200)
  limiter=Limiter(lambda:self.now,capacity=1);limiter.take(('unrelated','opaque',1,3600));self.client.app.state.limiter=limiter
  before=self.snapshot();self.rejected(self.client.post('/auth/login',json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}));self.assertEqual(self.snapshot(),before)
 def test_refresh_sixty_ip_attempts_no_session_mutation_on_rejection(self):
  before=self.snapshot();headers={'Origin':'http://localhost:5173','Cookie':'refresh_token=invalid','X-CSRF-Token':'a'*64}
  for _ in range(60):self.assertEqual(self.client.post('/auth/refresh',headers=headers).status_code,401)
  self.rejected(self.client.post('/auth/refresh',headers=headers));self.assertEqual(self.snapshot(),before)
 def test_listing_and_report_user_quotas_do_not_affect_reads_or_other_users(self):
  self.assertEqual(self.client.patch('/users/me',headers=self.headers,json={'phone':'+77001234567'}).status_code,200)
  body={'title':'Security textbook','description':'A useful item for security testing.','price':'1.00','category_id':1,'condition':'used'}
  for _ in range(10):self.assertEqual(self.client.post('/listings',headers=self.headers,json=body).status_code,201)
  before=self.snapshot();self.rejected(self.client.post('/listings',headers=self.headers,json=body));self.assertEqual(self.snapshot(),before);self.assertEqual(self.client.get('/listings/mine',headers=self.headers).status_code,200)
  self.assertEqual(self.client.patch('/users/me',headers=self.buyer_headers,json={'phone':'+77001234567'}).status_code,200);self.assertEqual(self.client.post('/listings',headers=self.buyer_headers,json=body).status_code,201)
  for _ in range(10):self.assertEqual(self.client.post(f'/listings/{self.item.id}/reports',headers=self.buyer_headers,json={'reason':'spam'}).status_code,202)
  before=self.snapshot();self.rejected(self.client.post(f'/listings/{self.item.id}/reports',headers=self.buyer_headers,json={'reason':'spam'}));self.assertEqual(self.snapshot(),before)
 def test_avatar_and_listing_upload_share_thirty_quota_no_file_mutation_on_reject(self):
  for _ in range(30):self.assertEqual(self.client.post('/users/me/avatar',headers=self.headers,files={'image':('photo.png',fixture.picture(),'image/png')}).status_code,200)
  with self.database.session() as s:path=s.get(User,self.owner.id).avatar_path
  file=ImageStorage(self.settings.upload_dir).path(path,self.owner.id);before=file.read_bytes();snapshot=self.snapshot()
  self.rejected(self.client.post(f'/listings/{self.item.id}/photos',headers=self.headers,files={'image':('bad.png',b'invalid','image/png')}));self.assertEqual(file.read_bytes(),before);self.assertEqual(self.snapshot(),snapshot)
 def test_sensitive_headers_cors_and_stream_overflow_preserve_database(self):
  for path,headers in [('/auth/me',self.headers),('/users/me',self.headers),(f'/listings/{self.item.id}/photos/{self.photo.id}',self.buyer_headers),('/admin/me',self.headers)]:
   result=self.client.get(path,headers=headers);self.assertEqual(result.headers['Cache-Control'],'private, no-store');self.assertEqual(result.headers['X-Content-Type-Options'],'nosniff')
  before=self.snapshot();response=self.client.post('/auth/register',headers={'Content-Length':'1','Content-Type':'application/json','Origin':'http://localhost:5173'},content=(b'x'*32768 for _ in range(3)));self.assertEqual(response.status_code,413);self.assertEqual(response.headers['Access-Control-Allow-Origin'],'http://localhost:5173');self.assertEqual(self.snapshot(),before)
