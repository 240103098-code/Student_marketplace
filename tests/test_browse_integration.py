from datetime import timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch
from sqlalchemy import delete,select
from sqlalchemy.exc import SQLAlchemyError
import test_sold_integration as fixture
from backend.models import Listing,ListingPhoto,User,RefreshSession
from backend.sessions import revoke_user_sessions

class BrowsePostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def browse(self,query='',headers=None):return self.client.get('/listings'+query,headers=self.buyer_headers if headers is None else headers)
 def add(self,state='active',owner=None,published=None):
  with self.database.session() as s:
   row=Listing(owner_id=owner or self.owner.id,category_id=2,title='Private-safe card',description='SECRET_FULL_DESCRIPTION',price=Decimal('0.10'),condition='new',status=state,published_at=(published or self.now) if state in ['active','sold'] else None,rejection_reason='SECRET_REASON' if state=='rejected' else None);s.add(row);s.flush();return row.id
 def test_visibility_all_states_and_current_seller_eligibility(self):
  hidden=[self.add(state) for state in ['pending','sold','rejected','removed']]
  visible=self.add()
  for verified,suspended in [(False,False),(True,True)]:
   with self.database.session() as s:
    owner=User(email=f'seller{verified}{suspended}@sdu.edu.kz',password_hash='SECRET_HASH',verified=verified,suspended=suspended);s.add(owner);s.flush();owner_id=owner.id
   hidden.append(self.add(owner=owner_id))
  result=self.browse().json();self.assertEqual({r['id'] for r in result['items']},{self.item.id,visible});self.assertEqual(result['total'],2)
  self.assertEqual({r['id'] for r in self.browse(headers=self.headers).json()['items']},{self.item.id,visible})
  with self.database.session() as s:s.get(User,self.owner.id).suspended=True
  self.assertEqual(self.browse().json()['total'],0)
  with self.database.session() as s:s.get(User,self.owner.id).suspended=False;s.get(User,self.owner.id).verified=False
  self.assertEqual(self.browse().json()['items'],[])
  with self.database.session() as s:s.delete(s.get(User,self.owner.id))
  self.assertEqual(self.browse().json()['total'],0)
 def test_publication_order_ties_pages_counts_and_no_mutations(self):
  older=self.add(published=self.now-timedelta(days=1));tie=self.add();new=self.add(published=self.now+timedelta(seconds=1));expected=[new,tie,self.item.id,older]
  result=self.browse('?limit=2').json();self.assertEqual([i['id'] for i in result['items']],expected[:2]);self.assertEqual((result['total'],result['count'],result['limit'],result['offset']),(4,2,2,0))
  self.assertEqual([i['id'] for i in self.browse('?limit=2&offset=2').json()['items']],expected[2:])
  beyond=self.browse('?offset=9223372036854775807').json();self.assertEqual(beyond['items'],[]);self.assertEqual(beyond['total'],4)
  defaults=self.browse().json();self.assertEqual(defaults['limit'],20);self.assertEqual(defaults['offset'],0)
  self.assertEqual(self.client.get('/listings/mine',headers=self.headers).json()['total'],4)
 def test_card_allowlist_canonical_price_and_lowest_position_photo(self):
  with self.database.session() as s:
   s.get(ListingPhoto,self.photo.id).position=3;s.flush();first=ListingPhoto(listing_id=self.item.id,position=2,storage_path=f'listings/{self.item.id}/'+ 'f'*32+'.png');s.add(first);s.flush();first_id=first.id
  no_photo=self.add();cards={c['id']:c for c in self.browse().json()['items']};card=cards[self.item.id]
  self.assertEqual(set(card),{'id','title','price','currency','category_id','condition','published_at','main_photo'});self.assertEqual(card['price'],'12.34');self.assertEqual(cards[no_photo]['price'],'0.10');self.assertIsNone(cards[no_photo]['main_photo'])
  self.assertEqual(card['main_photo'],{'id':first_id,'position':2,'is_main':True,'url':f'/listings/{self.item.id}/photos/{first_id}'})
  raw=self.browse().text
  for forbidden in ['SECRET','storage_path','owner_id','rejection_reason','email','password','description','verified','suspended']:self.assertNotIn(forbidden,raw)
  self.assertEqual(self.client.get(f'/listings/{self.item.id}/photos/{self.photo.id}',headers=self.buyer_headers).status_code,200)
 def test_strict_query_bounds_duplicates_and_unknowns(self):
  for query in ['?limit=0','?limit=51','?limit=-1','?limit=1.5','?limit=01','?offset=-1','?offset=9223372036854775808','?offset=1e3','?offset=','?limit=2&limit=3','?offset=0&offset=0','?status=active','?owner_id=1','?sort=id','?q=book','?category_id=1','?offset=%2B1','?limit='+('9'*5000)]:
   with self.subTest(query=query[:80]):
    result=self.browse(query);self.assertEqual(result.status_code,422);self.assertEqual(result.json(),{'detail':'Invalid marketplace query.'})
  self.assertEqual(self.browse('?limit=50&offset=0').status_code,200)
 def test_current_viewer_authentication_and_session_expiry(self):
  self.assertEqual(self.browse(headers={}).status_code,401)
  for field,value in [('verified',False),('suspended',True)]:
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,value)
   self.assertEqual(self.browse().status_code,401)
   with self.database.session() as s:setattr(s.get(User,self.buyer.id),field,not value)
  self.client.app.state.clock=lambda:self.now+timedelta(minutes=15)
  self.assertEqual(self.browse().status_code,401);self.client.app.state.clock=lambda:self.now
  with self.database.session() as s:
   for row in s.scalars(select(RefreshSession).where(RefreshSession.user_id==self.buyer.id)):row.created_at=self.now-timedelta(seconds=1);row.expires_at=self.now
  self.assertEqual(self.browse().status_code,401)
  self.buyer_headers={'Authorization':'Bearer '+self.login(self.buyer.email)}
  with self.database.session() as s:revoke_user_sessions(s,self.buyer.id,self.now)
  self.assertEqual(self.browse().status_code,401)
  self.buyer_headers={'Authorization':'Bearer '+self.login(self.buyer.email)}
  with self.database.session() as s:s.delete(s.get(User,self.buyer.id))
  self.assertEqual(self.browse().status_code,401)
 def test_empty_feed_and_sanitized_database_failure(self):
  with self.database.session() as s:s.execute(delete(Listing))
  self.assertEqual(self.browse().json(),{'items':[],'total':0,'count':0,'limit':20,'offset':0})
  with patch('backend.routers.listings.browse_listings_page',side_effect=SQLAlchemyError('SECRET_DRIVER')):
   result=self.browse();self.assertEqual(result.status_code,500);self.assertNotIn('SECRET',result.text);self.assertEqual(result.json(),{'detail':'Listings are temporarily unavailable.'})
 def test_viewer_revoked_between_guard_and_feed_read_is_rechecked(self):
  from threading import Event
  from concurrent.futures import ThreadPoolExecutor
  from backend.listings import browse_listings_page
  ready,release=Event(),Event()
  def pause(*args,**kwargs):ready.set();release.wait(5);return browse_listings_page(*args,**kwargs)
  with patch('backend.routers.listings.browse_listings_page',side_effect=pause):
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(self.browse);self.assertTrue(ready.wait(5))
    with self.database.session() as s:revoke_user_sessions(s,self.buyer.id,self.now)
    release.set();result=future.result(timeout=5);self.assertEqual(result.status_code,401);self.assertNotIn('items',result.json())
