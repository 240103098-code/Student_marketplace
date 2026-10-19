import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request
from backend.abuse import Limiter,RateLimited
from backend.security_boundary import SecurityBoundary
from backend.image_uploads import read_image_upload
from backend.images import FORM_LIMIT

class LimiterTest(unittest.TestCase):
 def setUp(self):self.now=datetime(2026,10,19,tzinfo=timezone.utc);self.limiter=Limiter(lambda:self.now,capacity=3)
 def test_exact_window_atomic_concurrency_and_composite_rejection(self):
  def take(_):
   try:self.limiter.take(('sample','sensitive@example.invalid',10,60));return True
   except RateLimited:return False
  with ThreadPoolExecutor(max_workers=20) as pool:self.assertEqual(sum(pool.map(take,range(50))),10)
  with self.assertRaises(RateLimited) as error:self.limiter.take(('other','new',2,60),('sample','sensitive@example.invalid',10,60))
  self.assertEqual(error.exception.retry,60);self.assertEqual(len(self.limiter._entries),1)
  self.now+=timedelta(seconds=59)
  with self.assertRaises(RateLimited) as error:self.limiter.take(('sample','sensitive@example.invalid',10,60))
  self.assertEqual(error.exception.retry,1);self.now+=timedelta(seconds=1);self.assertTrue(take(0))
 def test_capacity_fails_closed_no_eviction_prunes_and_hashes_identity(self):
  for n in range(3):self.limiter.take(('email',f'private{n}@sdu.edu.kz',5,60))
  before=dict(self.limiter._entries)
  with self.assertRaises(RateLimited):self.limiter.take(('email','new@sdu.edu.kz',5,60))
  self.assertEqual(before,self.limiter._entries);self.assertTrue(all(isinstance(key,bytes) and len(key)==32 for key in before));self.assertNotIn('private',repr(before));self.now+=timedelta(seconds=60);self.limiter.take(('email','new@sdu.edu.kz',5,60));self.assertEqual(len(self.limiter._entries),1)
 def test_success_refunds_only_own_reservation_not_other_failures_or_new_window(self):
  successful=self.limiter.take(('login','key',10,60));self.limiter.take(('login','key',10,60));self.limiter.refund(successful);self.assertEqual(next(iter(self.limiter._entries.values())).count,1)
  self.now+=timedelta(seconds=60);self.limiter.take(('login','key',10,60));self.limiter.refund(successful);self.assertEqual(next(iter(self.limiter._entries.values())).count,1)

class StreamingBoundaryTest(unittest.IsolatedAsyncioTestCase):
 async def run_request(self,chunks,path='/auth/login',peer='127.0.0.1',headers=None,limiter=None):
  messages=[];read=[];forwarded=[]
  async def receive():read.append(True);return chunks.pop(0)
  async def send(m):messages.append(m)
  async def application(scope,receive,send):forwarded.append(await receive());await send({'type':'http.response.start','status':200,'headers':[]});await send({'type':'http.response.body','body':b'{}'})
  scope={'type':'http','http_version':'1.1','method':'POST','scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','headers':headers or [(b'content-type',b'application/json'),(b'content-length',b'1')],'client':(peer,123),'server':('test',80)}
  limiter=limiter or Limiter(lambda:datetime(2026,10,19,tzinfo=timezone.utc))
  await SecurityBoundary(application,limiter)(scope,receive,send)
  return messages,read,forwarded
 async def test_real_json_bytes_overflow_stops_before_remainder_despite_false_content_length(self):
  chunks=[{'type':'http.request','body':b'x'*32768,'more_body':True},{'type':'http.request','body':b'x'*32769,'more_body':True},{'type':'http.request','body':b'NEVER_READ','more_body':False}]
  messages,read,forwarded=await self.run_request(chunks);self.assertEqual(messages[0]['status'],413);self.assertEqual(len(read),2);self.assertEqual(forwarded,[]);self.assertEqual(len(chunks),1)
  self.assertIn((b'cache-control',b'private, no-store'),messages[0]['headers']);self.assertIn((b'x-content-type-options',b'nosniff'),messages[0]['headers'])
 async def test_exact_json_boundary_and_abort(self):
  m,r,f=await self.run_request([{'type':'http.request','body':b' '*65536}]);self.assertEqual(m[0]['status'],200);self.assertEqual(len(f[0]['body']),65536)
  m,r,f=await self.run_request([{'type':'http.request','body':b'partial','more_body':True},{'type':'http.disconnect'}]);self.assertEqual(m[0]['status'],400);self.assertFalse(f)
 async def test_actual_peer_not_spoofed_headers_and_capacity_rejection(self):
  limiter=Limiter(lambda:datetime(2026,10,19,tzinfo=timezone.utc))
  for n in range(11):
   m,_,_=await self.run_request([{'type':'http.request','body':b'{}'}],path='/auth/register',headers=[(b'x-forwarded-for',f'10.0.0.{n}'.encode())],limiter=limiter)
   self.assertEqual(m[0]['status'],200 if n<10 else 429)
  m,_,_=await self.run_request([{'type':'http.request','body':b'{}'}],path='/auth/register',peer='127.0.0.2',limiter=limiter);self.assertEqual(m[0]['status'],200)
 async def test_multipart_overflow_abort_and_malformed_close_allocated_spools(self):
  beginning=b'--test\r\nContent-Disposition: form-data; name="image"; filename="x.png"\r\nContent-Type: image/png\r\n\r\n'
  for end,expected in [('overflow',413),('abort',400),('malformed',400)]:
   chunks=[{'type':'http.request','body':beginning+b'x'*1100000,'more_body':True}]
   if end=='overflow':chunks.extend([{'type':'http.request','body':b'x'*(FORM_LIMIT-1100000),'more_body':True},{'type':'http.request','body':b'NEVER','more_body':False}])
   elif end=='abort':chunks.append({'type':'http.disconnect'})
   else:chunks.append({'type':'http.request','body':b'','more_body':False})
   handles=[]
   def spool(*a,**k):f=tempfile.SpooledTemporaryFile(*a,**k);handles.append(f);return f
   async def receive():return chunks.pop(0)
   request=Request({'type':'http','headers':[(b'content-type',b'multipart/form-data; boundary=test')]},receive)
   with patch('starlette.formparsers.SpooledTemporaryFile',side_effect=spool):
    with self.assertRaises(HTTPException) as error:await read_image_upload(request)
   self.assertEqual(error.exception.status_code,expected);self.assertTrue(handles);self.assertTrue(all(f.closed for f in handles))

 async def test_multipart_content_type_cannot_bypass_json_route_limit(self):
  m,r,f=await self.run_request([{'type':'http.request','body':b'x'*65537}],path='/auth/login',headers=[(b'content-type',b'multipart/form-data; boundary=fake')]);self.assertEqual(m[0]['status'],413);self.assertFalse(f)
