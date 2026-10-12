from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from backend.config import REPOSITORY_ROOT
from backend.models import CATEGORIES, Category, EmailCode, Listing, ListingPhoto, ListingReport, RefreshSession, User
from postgresql_support import open_disposable_database


class ListingSchemaPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings, cls.database, _ = open_disposable_database()
        cls.addClassCleanup(cls.database.dispose)
        cls.configuration = Config(str(REPOSITORY_ROOT/'alembic.ini'))
        cls.configuration.attributes['settings'] = cls.settings
        command.upgrade(cls.configuration,'head')
        cls.addClassCleanup(command.downgrade,cls.configuration,'0001_baseline')

    def setUp(self):
        with self.database.session() as session:
            self.owner=User(email='seller@sdu.edu.kz',password_hash='SYNTHETIC_SCHEMA_HASH',verified=True)
            self.reporter=User(email='reporter@sdu.edu.kz',password_hash='SYNTHETIC_SCHEMA_HASH',verified=True)
            session.add_all([self.owner,self.reporter]);session.flush()

    def tearDown(self):
        with self.database.session() as session:session.execute(delete(User))

    def listing(self,**changes):
        with self.database.session() as session:
            item=Listing(**({'owner_id':self.owner.id,'category_id':1,'title':'Useful book','description':'A useful textbook.','price':Decimal('12.34'),'condition':'used'}|changes))
            session.add(item);session.flush()
            return item

    def photo(self,listing_id,position,path=None):
        with self.database.session() as session:
            item=ListingPhoto(listing_id=listing_id,position=position,storage_path=path or f'listings/{listing_id}/{uuid.uuid4().hex}.png')
            session.add(item);session.flush();return item

    def report(self,listing_id,**values):
        with self.database.session() as session:
            item=ListingReport(**({'listing_id':listing_id,'reporter_id':self.reporter.id,'reason':'spam'}|values))
            session.add(item);session.flush();return item

    def test_fixed_seed_categories_and_pending_kzt_defaults(self):
        with self.database.session() as session:
            self.assertEqual([(c.id,c.key,c.name) for c in session.scalars(select(Category).order_by(Category.id))],list(CATEGORIES))
        item=self.listing(title='  Useful book  ')
        self.assertEqual(item.title,'Useful book')
        self.assertEqual(item.status,'pending');self.assertEqual(item.currency,'KZT');self.assertIsNone(item.published_at)
        self.assertIsNotNone(item.created_at.tzinfo)
        with self.database.session() as session:self.assertEqual(session.get(Listing,item.id).price,Decimal('12.34'))
        with self.assertRaises(SQLAlchemyError):
            with self.database.session() as session:session.add(Category(id=6,key='extra',name='Extra'))

    def test_listing_field_fk_currency_condition_and_price_constraints(self):
        invalid=[{'title':'ab'},{'title':'x'*121},{'title':None},{'description':'x'*9},{'description':'x'*2001},{'description':None},{'owner_id':-1},{'category_id':-1},{'owner_id':None},{'price':Decimal('-0.01')},{'price':Decimal('1000000000.01')},{'price':Decimal('NaN')},{'price':None},{'currency':'USD'},{'condition':'broken'},{'condition':None}]
        for values in invalid:
            with self.subTest(fields=tuple(values)),self.assertRaises(SQLAlchemyError):self.listing(**values)
        for title in [' untrimmed','untrimmed ','\tuntrimmed','untrimmed\n']:
            with self.assertRaises(SQLAlchemyError):
                with self.database.session() as session:
                    session.execute(text("INSERT INTO listings(owner_id,category_id,title,description,price,condition) VALUES (:owner,1,:title,'Long description',1,'new')"),{'owner':self.owner.id,'title':title})
        for price in [Decimal('0.00'),Decimal('1000000000.00')]:self.assertEqual(self.listing(price=price).price,price)
        self.listing(title='x'*120,description='x'*2000,condition='new')
        rounded=self.listing(price=Decimal('1.005'))
        with self.database.session() as session:self.assertEqual(session.get(Listing,rounded.id).price,Decimal('1.01'))

    def test_supported_publication_and_rejection_states(self):
        now=datetime.now(timezone.utc)
        for status in ['active','sold']:
            with self.assertRaises(SQLAlchemyError):self.listing(status=status)
            item=self.listing(status=status,published_at=now)
            self.assertEqual(item.published_at,now)
        for status in ['hidden','paused','expired','unknown']:
            with self.assertRaises(SQLAlchemyError):self.listing(status=status)
        for reason in [None,'','   ','\t\n','x'*301]:
            with self.assertRaises(SQLAlchemyError):self.listing(status='rejected',rejection_reason=reason)
        self.assertEqual(self.listing(status='rejected',rejection_reason='Item is prohibited.').status,'rejected')
        self.assertEqual(self.listing(status='removed').status,'removed')
        with self.assertRaises(SQLAlchemyError):self.listing(status='pending',published_at=now)

    def test_photo_positions_uniqueness_safe_paths_and_derived_main(self):
        item=self.listing()
        third=self.photo(item.id,3);first=self.photo(item.id,1)
        for position in [0,6]:
            with self.assertRaises(SQLAlchemyError):self.photo(item.id,position)
        with self.assertRaises(SQLAlchemyError):self.photo(item.id,1)
        for path in ['../outside.png','/absolute.png','https://example.test/photo.png',f'listings/{item.id}/bad-name.png',f'listings/{item.id+1}/{uuid.uuid4().hex}.png']:
            with self.assertRaises(SQLAlchemyError):self.photo(item.id,2,path)
        with self.assertRaises(SQLAlchemyError):self.photo(item.id,2,first.storage_path)
        second=self.photo(item.id,2)
        for position in [4,5]:self.photo(item.id,position)
        with self.assertRaises(SQLAlchemyError):self.photo(item.id,5)
        with self.database.session() as session:
            ordered=list(session.scalars(select(ListingPhoto).where(ListingPhoto.listing_id==item.id).order_by(ListingPhoto.position)))
            self.assertEqual([p.position for p in ordered],[1,2,3,4,5]);self.assertEqual(ordered[0].id,first.id)
        with self.assertRaises(SQLAlchemyError):self.photo(-1,1)

    def test_basic_report_reasons_review_timestamps_and_foreign_keys(self):
        item=self.listing();now=datetime.now(timezone.utc)
        for reason in ['spam','prohibited_items','misleading_information']:
            report=self.report(item.id,reason=reason)
            self.assertIsNotNone(report.created_at.tzinfo);self.assertIsNone(report.reviewed_at)
        self.report(item.id,created_at=now,reviewed_at=now+timedelta(seconds=1))
        for values in [{'reason':'user_issue'},{'reason':''},{'reason':None},{'reporter_id':-1},{'listing_id':-1},{'created_at':now,'reviewed_at':now-timedelta(seconds=1)}]:
            with self.assertRaises(SQLAlchemyError):self.report(item.id,**values) if 'listing_id' not in values else self.report(values['listing_id'])

    def test_owner_reporter_cascades_and_restricted_category_deletion(self):
        item=self.listing();photo=self.photo(item.id,1);report=self.report(item.id)
        with self.assertRaises(SQLAlchemyError):
            with self.database.session() as session:session.delete(session.get(Category,1))
        with self.database.session() as session:session.delete(session.get(User,self.reporter.id))
        with self.database.session() as session:
            self.assertIsNone(session.get(ListingReport,report.id));self.assertIsNotNone(session.get(Listing,item.id));self.assertIsNotNone(session.get(ListingPhoto,photo.id))
            another=User(email='another@sdu.edu.kz',password_hash='SYNTHETIC_SCHEMA_HASH');session.add(another);session.flush()
            second=ListingReport(reporter_id=another.id,listing_id=item.id,reason='spam');session.add(second);session.flush();second_id=second.id
        with self.database.session() as session:session.delete(session.get(User,self.owner.id))
        with self.database.session() as session:
            self.assertIsNone(session.get(Listing,item.id));self.assertIsNone(session.get(ListingPhoto,photo.id));self.assertIsNone(session.get(ListingReport,second_id));self.assertEqual(session.scalar(select(func.count()).select_from(Category)),5)

    def test_indexes_and_upgrade_downgrade_reupgrade_preserve_accounts(self):
        now=datetime.now(timezone.utc)
        with self.database.session() as session:
            session.add(EmailCode(user_id=self.owner.id,purpose='registration',digest='a'*64,expires_at=now+timedelta(minutes=10)))
            session.add(RefreshSession(user_id=self.owner.id,token_digest='b'*64,expires_at=now+timedelta(days=7)))
        with self.database.engine.connect() as connection:
            inspector=inspect(connection)
            self.assertIn('ix_listings_owner_status',{i['name'] for i in inspector.get_indexes('listings')})
            self.assertIn('ix_listings_active_publication',{i['name'] for i in inspector.get_indexes('listings')})
            self.assertIn('uq_listing_photos_slot',{i['name'] for i in inspector.get_unique_constraints('listing_photos')})
            self.assertIn('ix_listing_reports_unreviewed',{i['name'] for i in inspector.get_indexes('listing_reports')})
            self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),'0003_listings')
        command.downgrade(self.configuration,'0002_accounts')
        with self.database.engine.connect() as connection:self.assertEqual(set(inspect(connection).get_table_names()),{'alembic_version','users','email_codes','refresh_sessions'})
        with self.database.session() as session:
            self.assertEqual(session.get(User,self.owner.id).email,self.owner.email)
            self.assertEqual(session.scalar(select(func.count()).select_from(EmailCode)),1)
            self.assertEqual(session.scalar(select(func.count()).select_from(RefreshSession)),1)
        command.upgrade(self.configuration,'head')
        with self.database.session() as session:self.assertEqual([(c.id,c.key,c.name) for c in session.scalars(select(Category).order_by(Category.id))],list(CATEGORIES))
        self.listing()
