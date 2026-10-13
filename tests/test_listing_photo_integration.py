from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Event
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.config import REPOSITORY_ROOT
from backend.images import ImageStorage, ImageStorageError, MAX_BYTES
from backend.listing_photos import append_listing_photo
from backend.models import Listing, ListingPhoto, User
from backend.sessions import revoke_user_sessions
from postgresql_support import open_disposable_database
from test_avatar_integration import picture


class ListingPhotoPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings,cls.database,_=open_disposable_database();cls.addClassCleanup(cls.database.dispose)
        cls.configuration=Config(str(REPOSITORY_ROOT/'alembic.ini'));cls.configuration.attributes['settings']=cls.settings
        command.upgrade(cls.configuration,'head');cls.addClassCleanup(command.downgrade,cls.configuration,'0001_baseline')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='listing-photo-disposable-');self.root=Path(self.temp.name)/'uploads'
        self.settings=self.settings.model_copy(update={'upload_dir':self.root})
        self.now=datetime(2026,10,12,12,tzinfo=timezone.utc)
        self.context=TestClient(create_app(self.settings,self.database,clock=lambda:self.now));self.client=self.context.__enter__()
        with self.database.session() as session:
            self.owner=User(email='seller@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_PHOTO_PASSWORD_123'),verified=True)
            self.buyer=User(email='buyer@sdu.edu.kz',password_hash=PasswordHasher().hash('TEST_PHOTO_PASSWORD_123'),verified=True)
            session.add_all([self.owner,self.buyer]);session.flush()
            self.listing=Listing(owner_id=self.owner.id,category_id=1,title='Useful book',description='A useful textbook.',price=Decimal('12.34'),condition='used')
            self.other=Listing(owner_id=self.buyer.id,category_id=2,title='Other item',description='Other description.',price=Decimal('2.00'),condition='new')
            session.add_all([self.listing,self.other]);session.flush()
        self.owner_headers={'Authorization':'Bearer '+self.login(self.owner.email)}
        self.buyer_headers={'Authorization':'Bearer '+self.login(self.buyer.email)}

    def tearDown(self):
        self.context.__exit__(None,None,None)
        with self.database.session() as session:session.execute(delete(User))
        self.temp.cleanup()

    def login(self,email):return self.client.post('/auth/login',json={'email':email,'password':'TEST_PHOTO_PASSWORD_123'}).json()['access_token']

    def upload(self,raw=None,listing=None,headers=None):
        id=self.listing.id if listing is None else listing
        return self.client.post(f'/listings/{id}/photos',files={'image':('../../SENSITIVE_ORIGINAL.svg',picture() if raw is None else raw,'image/svg+xml')},headers=self.owner_headers if headers is None else headers)

    def read(self,photo_id,headers=None,listing=None):return self.client.get(f'/listings/{self.listing.id if listing is None else listing}/photos/{photo_id}',headers=self.owner_headers if headers is None else headers)

    def photos(self):
        with self.database.session() as session:return list(session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id==self.listing.id).order_by(ListingPhoto.position)))

    def files(self):return {str(path.relative_to(self.root)):path.read_bytes() for path in self.root.rglob('*') if path.is_file()} if self.root.exists() else {}

    def state(self,value):
        with self.database.session() as session:
            item=session.get(Listing,self.listing.id);item.status=value
            item.published_at=self.now if value in {'active','sold'} else None
            item.rejection_reason='Not permitted.' if value=='rejected' else None

    def test_order_main_protected_dto_and_five_six_limit_no_file_changes(self):
        for position in range(1,6):
            result=self.upload();self.assertEqual(result.status_code,201);data=result.json()
            self.assertEqual(set(data),{'id','listing_id','position','is_main','url'})
            self.assertEqual(data['position'],position);self.assertEqual(data['is_main'],position==1)
            self.assertEqual(data['url'],f'/listings/{self.listing.id}/photos/{data["id"]}')
            self.assertNotIn('SENSITIVE',result.text);self.assertNotIn('storage_path',result.text)
            binary=self.read(data['id']);self.assertEqual(binary.status_code,200)
            self.assertEqual(binary.headers['content-type'],'image/png');self.assertEqual(binary.headers['cache-control'],'private, no-store')
        before=self.files();self.assertEqual(self.upload().status_code,409);self.assertEqual(self.files(),before)
        self.assertEqual([p.position for p in self.photos()],[1,2,3,4,5])

    def test_concurrent_fifth_upload_has_one_success_one_conflict(self):
        for _ in range(4):self.assertEqual(self.upload().status_code,201)
        before=self.files()
        with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(lambda _:self.upload(),range(2)))
        self.assertEqual(sorted(result.status_code for result in results),[201,409])
        self.assertEqual([p.position for p in self.photos()],[1,2,3,4,5])
        self.assertEqual(len(self.files()),5)
        for path,content in before.items():self.assertEqual(self.files()[path],content)

    def test_owner_pending_only_and_non_owned_missing_are_non_disclosing(self):
        self.assertEqual(self.upload(listing=self.other.id).status_code,404)
        self.assertEqual(self.upload(listing=999999).status_code,404)
        for state in ['active','sold','rejected','removed']:
            self.state(state);self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.photos(),[]);self.assertEqual(self.files(),{})

    def test_buyer_owner_states_seller_eligibility_and_linkage(self):
        id=self.upload().json()['id']
        other_id=self.upload(listing=self.other.id,headers=self.buyer_headers).json()['id']
        self.assertEqual(self.read(other_id).status_code,404)
        for state in ['pending','active','sold','rejected']:
            self.state(state);self.assertEqual(self.read(id).status_code,200)
            self.assertEqual(self.read(id,headers=self.buyer_headers).status_code,200 if state=='active' else 404)
        self.state('removed');self.assertEqual(self.read(id).status_code,404);self.assertEqual(self.read(id,headers=self.buyer_headers).status_code,404)
        self.state('active')
        for flag in ['verified','suspended']:
            with self.database.session() as session:setattr(session.get(User,self.owner.id),flag,flag=='suspended')
            self.assertEqual(self.read(id,headers=self.buyer_headers).status_code,404)
            with self.database.session() as session:setattr(session.get(User,self.owner.id),flag,flag=='verified')

    def test_invalid_image_overflow_multipart_and_paths_leave_existing_photos_intact(self):
        self.upload();before=self.files()
        for raw,status in [(b'NOT_IMAGE',400),(picture()+bytes(MAX_BYTES+1),413)]:
            self.assertEqual(self.upload(raw).status_code,status);self.assertEqual(self.files(),before)
        self.assertEqual(self.client.post(f'/listings/{self.listing.id}/photos',files={'wrong':('bad.png',picture())},headers=self.owner_headers).status_code,400)
        with self.database.session() as session:session.get(ListingPhoto,self.photos()[0].id).storage_path=f'listings/{self.listing.id}/'+'a'*32+'.png'
        self.assertEqual(self.read(self.photos()[0].id).status_code,404)
        storage=ImageStorage(self.root,namespace='listings')
        for path in ['../outside.png',f'avatars/{self.listing.id}/'+'a'*32+'.png',f'listings/{self.other.id}/'+'a'*32+'.png']:
            with self.assertRaises(ImageStorageError):storage.path(path,self.listing.id)
        self.assertEqual(self.files(),before)

    def test_commit_failure_cleans_new_file_preserves_existing_and_avatar_namespace(self):
        self.upload();self.client.post('/users/me/avatar',files={'image':('avatar.png',picture())},headers=self.owner_headers)
        before=self.files();original=Session.commit
        def failed_commit(session):
            if session.scalar(select(func.count()).select_from(ListingPhoto).where(ListingPhoto.listing_id==self.listing.id))>1:raise SQLAlchemyError('SENSITIVE_DRIVER')
            return original(session)
        with patch.object(Session,'commit',failed_commit):result=self.upload(picture('JPEG'))
        self.assertEqual(result.status_code,500);self.assertNotIn('SENSITIVE',result.text)
        self.assertEqual(self.files(),before);self.assertEqual(len(self.photos()),1)
        with patch.object(ImageStorage,'write',side_effect=ImageStorageError('SENSITIVE_PATH')):
            self.assertEqual(self.upload().status_code,500)
        self.assertEqual(self.files(),before)
        self.assertEqual(self.client.get('/users/me/avatar',headers=self.owner_headers).status_code,200)

    def test_stale_guard_rechecks_current_listing_state_ownership_and_revocation(self):
        for mutation,expected in [('state',409),('ownership',404),('revoke',401)]:
            self.owner_headers={'Authorization':'Bearer '+self.login(self.owner.email)};ready,release=Event(),Event()
            def paused(*args,**kwargs):
                ready.set()
                if not release.wait(5):raise RuntimeError('Test synchronization timed out')
                return append_listing_photo(*args,**kwargs)
            with patch('backend.routers.listing_photos.append_listing_photo',side_effect=paused):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending=executor.submit(self.upload);self.assertTrue(ready.wait(5))
                    try:
                        with self.database.session() as session:
                            listing=session.get(Listing,self.listing.id)
                            if mutation=='state':listing.status='active';listing.published_at=self.now
                            elif mutation=='ownership':listing.owner_id=self.buyer.id
                            else:revoke_user_sessions(session,self.owner.id,self.now)
                    finally:release.set()
                    self.assertEqual(pending.result(timeout=5).status_code,expected)
            with self.database.session() as session:
                listing=session.get(Listing,self.listing.id);listing.owner_id=self.owner.id;listing.status='pending';listing.published_at=None
        self.assertEqual(self.files(),{});self.assertEqual(self.photos(),[])

    def test_invalid_viewer_and_id_values_never_return_image_bytes(self):
        id=self.upload().json()['id']
        self.assertEqual(self.client.get(f'/listings/{self.listing.id}/photos/{id}').status_code,401)
        for flag in ['verified','suspended']:
            with self.database.session() as session:setattr(session.get(User,self.owner.id),flag,flag=='suspended')
            self.assertEqual(self.read(id).status_code,401)
            with self.database.session() as session:setattr(session.get(User,self.owner.id),flag,flag=='verified')
        for listing,photo in [(-1,id),(self.listing.id,0),(self.listing.id,2**63)]:self.assertEqual(self.read(photo,listing=listing).status_code,422)
        with self.database.session() as session:revoke_user_sessions(session,self.owner.id,self.now)
        self.assertEqual(self.read(id).status_code,401);self.assertEqual(self.upload().status_code,401)
