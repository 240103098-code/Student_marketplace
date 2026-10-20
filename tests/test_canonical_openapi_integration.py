import unittest
from backend.admin import promote_existing_admin
from backend.models import Listing,User
import test_sold_integration as fixture
from test_avatar_integration import picture
from contract_support import assert_response,validate_json

class CanonicalContractPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def check(self,path,method,response,status):assert_response(self,self.client.app.openapi(),path,method,response,status);return response
 def test_actual_manual_create_edit_upload_binary_actions_and_admin_report_contracts(self):
  document=self.client.app.openapi()
  self.check('/users/me','patch',self.client.patch('/users/me',headers=self.headers,json={'phone':'+77001234567'}),200)
  payload={'title':'Canonical sample book','description':'A synthetic canonical contract item.','price':'12.3400','category_id':3,'condition':'used'}
  validate_json(document,document['paths']['/listings']['post']['requestBody']['content']['application/json']['schema'],payload)
  response=self.check('/listings','post',self.client.post('/listings',headers=self.headers,json=payload),201);id=response.json()['id']
  self.check('/listings','post',self.client.post('/listings',headers=self.headers,json={**payload,'owner_id':self.buyer.id}),422)
  self.check('/listings','post',self.client.post('/listings',headers={**self.headers,'Content-Type':'application/json'},content='{"title":"bad","title":"duplicate"}'),422)
  self.check('/listings/{listing_id}','patch',self.client.patch(f'/listings/{id}',headers=self.headers,json={'price':'10.00'}),200)
  self.check('/listings/{listing_id}','patch',self.client.patch(f'/listings/{id}',headers=self.headers,json={'price':None}),422)
  upload=self.check('/listings/{listing_id}/photos','post',self.client.post(f'/listings/{id}/photos',headers=self.headers,files={'image':('sample.png',picture(),'image/png')}),201)
  photo=upload.json();binary=self.check('/listings/{listing_id}/photos/{photo_id}','get',self.client.get(photo['url'],headers=self.headers),200);self.assertTrue(binary.content.startswith(b'\x89PNG'))
  self.check('/listings/{listing_id}/photos','post',self.client.post(f'/listings/{id}/photos',headers=self.headers,files={'file':('sample.png',picture(),'image/png')}),400)
  self.check('/listings/{listing_id}/photos/{photo_id}','get',self.client.get(photo['url'],headers=self.buyer_headers),404)
  promote_existing_admin(self.database,self.buyer.email)
  self.check('/admin/me','get',self.client.get('/admin/me',headers=self.buyer_headers),200)
  self.check('/admin/listings/{listing_id}','get',self.client.get(f'/admin/listings/{id}',headers=self.buyer_headers),200)
  self.check('/admin/listings/{listing_id}/photos/{photo_id}','get',self.client.get(f'/admin/listings/{id}/photos/{photo["id"]}',headers=self.buyer_headers),200)
  self.check('/admin/listings/{listing_id}/approve','post',self.client.post(f'/admin/listings/{id}/approve',headers=self.buyer_headers,json={'status':'active'}),422)
  self.check('/admin/listings/{listing_id}/approve','post',self.client.post(f'/admin/listings/{id}/approve',headers=self.buyer_headers,json={}),200)
  self.check('/listings','get',self.client.get('/listings?min_price=10.00&max_price=10.00',headers=self.headers),200)
  self.check('/listings','get',self.client.get('/listings?limit=01',headers=self.headers),422)
  self.check('/listings','get',self.client.get('/listings?limit=1&limit=1',headers=self.headers),422)
  self.check('/listings/{listing_id}/reports','post',self.client.post(f'/listings/{id}/reports',headers=self.buyer_headers,json={'reason':'spam'}),202)
  reports=self.check('/admin/reports','get',self.client.get('/admin/reports',headers=self.buyer_headers),200)
  report_id=next(r['id'] for r in reports.json()['items'] if r['listing']['id']==id)
  self.check('/admin/reports/{report_id}/review','post',self.client.post(f'/admin/reports/{report_id}/review',headers=self.buyer_headers),200)
  self.check('/listings/{listing_id}/sold','post',self.client.post(f'/listings/{id}/sold',headers=self.headers),200)
  self.check('/admin/listings/{listing_id}/remove','post',self.client.post(f'/admin/listings/{id}/remove',headers=self.buyer_headers),200)
  self.check('/listings/{listing_id}','delete',self.client.delete(f'/listings/{id}',headers=self.headers),200)
 def test_actual_cookie_csrf_capability_and_rejection_response_contracts(self):
  origin=self.settings.frontend_origins[0]
  response=self.check('/auth/login','post',self.client.post('/auth/login',headers={'Origin':origin},json={'email':self.owner.email,'password':'TEST_SOLD_PASSWORD_123'}),200)
  cookie=response.headers['set-cookie'].lower()
  for field in ['refresh_token=','httponly','path=/auth','samesite=lax']:self.assertIn(field,cookie)
  access={'Authorization':'Bearer '+response.json()['access_token']}
  self.check('/auth/me','get',self.client.get('/auth/me',headers=access),200)
  csrf=self.check('/auth/csrf','get',self.client.get('/auth/csrf',headers={'Origin':origin}),200).json()['csrf_token']
  self.check('/auth/refresh','post',self.client.post('/auth/refresh',headers={'Origin':origin}),403)
  self.check('/auth/refresh','post',self.client.post('/auth/refresh',headers={'Origin':origin,'X-CSRF-Token':csrf}),200)
  self.check('/auth/logout','post',self.client.post('/auth/logout',headers={'Origin':origin,'X-CSRF-Token':csrf}),204)
  self.check('/auth/me','get',self.client.get('/auth/me',headers=access),401)
  promote_existing_admin(self.database,self.buyer.email)
  with self.database.session() as session:
   listing=session.get(Listing,self.item.id);listing.status='pending';listing.published_at=None
  self.check('/admin/listings/{listing_id}/reject','post',self.client.post(f'/admin/listings/{self.item.id}/reject',headers=self.buyer_headers,json={'reason':'  Clear private feedback  '}),200)
  self.check('/admin/users/{target_id}/suspension','patch',self.client.patch(f'/admin/users/{self.owner.id}/suspension',headers=self.buyer_headers,json={'suspended':True}),200)
