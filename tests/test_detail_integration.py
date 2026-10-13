import unittest
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.models import User,Listing,ListingPhoto
from backend.sessions import revoke_user_sessions

class DetailPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def detail(self,headers=None,id=None):return self.client.get(f'/listings/{id or self.item.id}',headers=self.buyer_headers if headers is None else headers)
 def test_private_states_seller_eligibility_and_owner_same404(self):
  for state in ['pending','sold','rejected','removed']:
   with self.database.session() as s:
    row=s.get(Listing,self.item.id);row.status=state;row.published_at=self.now if state=='sold' else None;row.rejection_reason='Private' if state=='rejected' else None
   self.assertEqual(self.detail().status_code,404);self.assertEqual(self.detail(self.headers).status_code,404);self.assertEqual(self.client.get(f'/listings/{self.item.id}/edit',headers=self.headers).status_code,200)
  with self.database.session() as s:row=s.get(Listing,self.item.id);row.status='active';row.published_at=self.now
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,value)
   self.assertEqual(self.detail().status_code,404)
   with self.database.session() as s:setattr(s.get(User,self.owner.id),field,not value)
  self.assertEqual(self.detail().status_code,200)
  with self.database.session() as s:s.delete(s.get(User,self.owner.id))
  self.assertEqual(self.detail().status_code,404)
 def test_safe_fields_current_valid_contacts_and_ordered_photos(self):
  with self.database.session() as s:
   owner=s.get(User,self.owner.id);owner.name=' Seller ';owner.phone='+77001234567';owner.telegram_username='seller_name';owner.external_contact_url='https://example.com/contact';s.get(ListingPhoto,self.photo.id).position=3;s.flush();first=ListingPhoto(listing_id=self.item.id,position=2,storage_path=f'listings/{self.item.id}/'+ 'f'*32+'.png');s.add(first);s.flush();first_id=first.id
  result=self.detail();self.assertEqual(result.status_code,200);data=result.json();self.assertEqual(set(data),{'id','title','description','price','currency','category_id','condition','published_at','photos','seller'});self.assertEqual(data['price'],'12.34');self.assertEqual(data['seller'],{'name':'Seller','phone':'+77001234567','telegram_username':'seller_name','external_contact_url':'https://example.com/contact'});self.assertEqual([p['id'] for p in data['photos']],[first_id,self.photo.id]);self.assertEqual([p['is_main'] for p in data['photos']],[True,False]);self.assertEqual(data['photos'][0]['url'],f'/listings/{self.item.id}/photos/{first_id}')
  for key in ['email','verified','suspended','role','password_hash','owner_id','storage_path','rejection_reason','access_token']:self.assertNotIn(key,result.text)
  with self.database.session() as s:s.get(User,self.owner.id).phone=None;s.get(User,self.owner.id).telegram_username=None;s.get(User,self.owner.id).external_contact_url=None
  self.assertEqual(self.detail().json()['seller']['phone'],None)
 def test_invalid_legacy_contacts_are_null_not_links(self):
  for url in ['javascript:alert(1)','https://user:pass@example.com','https://example.com/a b']:
   with self.database.session() as s:
    owner=s.get(User,self.owner.id);owner.name=' ';owner.phone='123';owner.telegram_username='x@bad';owner.external_contact_url=url
   self.assertEqual(self.detail().json()['seller'],{'name':None,'phone':None,'telegram_username':None,'external_contact_url':None})
 def test_viewer_guard_revoked_and_safe_missing_ids(self):
  self.assertEqual(self.detail(headers={}).status_code,401);self.assertEqual(self.detail(id=9223372036854775807).status_code,404)
  for id in [0,9223372036854775808]:self.assertEqual(self.client.get(f'/listings/{id}',headers=self.buyer_headers).status_code,422)
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,value)
   self.assertEqual(self.detail().status_code,401)
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,not value)
  with self.database.session() as s:revoke_user_sessions(s,self.buyer.id,self.now)
  self.assertEqual(self.detail().status_code,401)
 def test_database_errors_do_not_expose_contacts_or_driver(self):
  with patch('backend.routers.listings.read_buyer_listing',side_effect=SQLAlchemyError('PRIVATE_DRIVER')):
   result=self.detail();self.assertEqual(result.status_code,500);self.assertEqual(result.json(),{'detail':'Listings are temporarily unavailable.'})
