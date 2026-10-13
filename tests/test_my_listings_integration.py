from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
import uuid

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.models import Listing, ListingPhoto, User
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database


class MyListingsPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings,cls.database,_=open_disposable_database();cls.addClassCleanup(cls.database.dispose)
        cls.configuration=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.configuration.attributes['settings']=cls.settings
        command.upgrade(cls.configuration,'head');cls.addClassCleanup(command.downgrade,cls.configuration,'0001_baseline')

    def setUp(self):
        self.now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        self.context=TestClient(create_app(self.settings,self.database,clock=lambda:self.now));self.client=self.context.__enter__()
        with self.database.session() as session:
            self.user=User(email='seller@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_MINE_PASSWORD_123'),verified=True)
            self.other=User(email='other@sdu.edu.kz',password_hash='SYNTHETIC_HASH',verified=True)
            session.add_all([self.user,self.other]);session.flush()
        login=self.client.post('/auth/login',json={'email':self.user.email,'password':'TEST_MINE_PASSWORD_123'})
        self.headers={'Authorization':'Bearer '+login.json()['access_token']}

    def tearDown(self):
        self.context.__exit__(None,None,None)
        with self.database.session() as session:session.execute(delete(User))

    def listing(self,status='pending',owner=None,created=None):
        with self.database.session() as session:
            item=Listing(owner_id=self.user.id if owner is None else owner,category_id=1,title='Useful book',description='A useful textbook.',price=Decimal('12.34'),condition='used',status=status,created_at=self.now if created is None else created,published_at=self.now if status in {'active','sold'} else None,rejection_reason='Prohibited item.' if status=='rejected' else None)
            session.add(item);session.flush();return item

    def get(self,query=''):return self.client.get('/listings/mine'+query,headers=self.headers)

    def test_owner_isolation_each_status_total_and_empty_page(self):
        owned={status:self.listing(status).id for status in ['pending','active','sold','rejected','removed']}
        for status in owned:self.listing(status,owner=self.other.id)
        result=self.get();self.assertEqual(result.status_code,200);data=result.json()
        self.assertEqual((data['total'],data['count'],data['limit'],data['offset'],data['status']),(5,5,20,0,None));self.assertEqual({i['id'] for i in data['items']},set(owned.values()))
        for status,id in owned.items():
            data=self.get('?status='+status).json();self.assertEqual((data['total'],data['count'],data['status']),(1,1,status));self.assertEqual(data['items'][0]['id'],id)
        empty=self.get('?offset=20&status=active').json();self.assertEqual((empty['total'],empty['count'],empty['items']),(1,0,[]))

    def test_stable_creation_then_id_sort_and_bounded_pagination(self):
        oldest=self.listing(created=self.now-timedelta(days=1))
        tied=[self.listing() for _ in range(24)]
        expected=[item.id for item in reversed(tied)]+[oldest.id]
        first=self.get().json();second=self.get('?offset=20').json()
        self.assertEqual([i['id'] for i in first['items']],expected[:20]);self.assertEqual([i['id'] for i in second['items']],expected[20:])
        self.assertEqual((first['total'],first['count'],second['total'],second['count']),(25,20,25,5))
        self.assertEqual(self.get('?limit=50').json()['count'],25)
        self.assertEqual(self.get('?limit=1&offset=1').json()['items'][0]['id'],expected[1])

    def test_strict_unknown_spoof_duplicate_and_invalid_queries_rejected(self):
        self.listing(owner=self.other.id)
        for query in ['?owner_id='+str(self.other.id),'?user_id='+str(self.other.id),'?email=other@sdu.edu.kz','?limit=0','?limit=51','?limit=-1','?offset=-1','?offset=1.5','?offset=true','?limit=01','?limit=20&limit=20','?status=Active','?status=unknown','?status=','?offset='+str(2**63)]:
            response=self.get(query);self.assertEqual(response.status_code,422);self.assertEqual(response.json(),{'detail':'Invalid My Listings query.'})
        self.assertEqual(self.get().json()['items'],[])

    def test_safe_ordered_photo_dto_and_removed_no_photo_urls(self):
        item=self.listing('rejected');removed=self.listing('removed')
        with self.database.session() as session:
            for listing in [item,removed]:
                for position in [3,1,2]:session.add(ListingPhoto(listing_id=listing.id,position=position,storage_path=f'listings/{listing.id}/{uuid.uuid4().hex}.png'))
        result=self.get();self.assertEqual(result.status_code,200);items={i['id']:i for i in result.json()['items']}
        rejection=items[item.id];self.assertEqual(rejection['rejection_reason'],'Prohibited item.')
        self.assertEqual([p['position'] for p in rejection['photos']],[1,2,3]);self.assertEqual([p['is_main'] for p in rejection['photos']],[True,False,False])
        for photo in rejection['photos']:self.assertEqual(photo['url'],f'/listings/{item.id}/photos/{photo["id"]}')
        self.assertEqual(items[removed.id]['photos'],[]);self.assertIsNone(items[removed.id]['rejection_reason'])
        self.assertNotIn('storage_path',result.text);self.assertNotIn('password',result.text);self.assertNotIn(self.user.email,result.text)
        self.assertEqual(rejection['price'],'12.34');self.assertEqual(rejection['currency'],'KZT')

    def test_missing_ineligible_revoked_and_expired_sessions_cannot_discover_own_items(self):
        self.listing();self.assertEqual(self.client.get('/listings/mine').status_code,401)
        for flag in ['verified','suspended']:
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='suspended')
            self.assertEqual(self.get().status_code,401)
            with self.database.session() as session:setattr(session.get(User,self.user.id),flag,flag=='verified')
        self.now+=timedelta(minutes=15);self.assertEqual(self.get().status_code,401);self.now-=timedelta(minutes=15)
        with self.database.session() as session:revoke_user_sessions(session,self.user.id,self.now)
        self.assertEqual(self.get().status_code,401)
        with self.database.session() as session:session.delete(session.get(User,self.user.id))
        self.assertEqual(self.get().status_code,401)

    def test_fixed_route_precedes_dynamic_and_empty_account_defaults(self):
        from backend.routers.listings import router
        paths=[route.path for route in router.routes]
        self.assertLess(paths.index('/listings/mine'),paths.index('/listings/{listing_id}/edit'))
        data=self.get().json();self.assertEqual(data,{'items':[],'total':0,'count':0,'limit':20,'offset':0,'status':None})
