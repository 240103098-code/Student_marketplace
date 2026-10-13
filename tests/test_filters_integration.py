from urllib.parse import urlencode
from decimal import Decimal
import unittest
import test_sold_integration as fixture
from backend.models import Listing,User

class FilterPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def add(self,price,category=2,condition='new',state='active',owner=None):
  with self.database.session() as s:
   row=Listing(owner_id=owner or self.owner.id,category_id=category,title='Matching needle',description='A useful description.',price=Decimal(price),condition=condition,status=state,published_at=self.now if state in ['active','sold'] else None,rejection_reason='Private' if state=='rejected' else None);s.add(row);s.flush();return row.id
 def feed(self,**filters):return self.client.get('/listings?'+urlencode(filters),headers=self.buyer_headers)
 def ids(self,**filters):return [r['id'] for r in self.feed(**filters).json()['items']]
 def test_individual_inclusive_equal_one_sided_zero_and_maximum(self):
  zero=self.add('0');middle=self.add('10.10');maximum=self.add('1000000000',category=5,condition='used')
  self.assertEqual(set(self.ids(category_id='2')),{zero,middle});self.assertEqual(set(self.ids(condition='used')),{self.item.id,maximum})
  self.assertEqual(set(self.ids(min_price='10.10')),{middle,self.item.id,maximum});self.assertEqual(set(self.ids(max_price='10.10')),{zero,middle})
  self.assertEqual(self.ids(min_price='10.1000',max_price='10.10'),[middle]);self.assertEqual(self.ids(min_price='0',max_price='0.000'),[zero]);self.assertEqual(self.ids(min_price='1000000000',max_price='1000000000.00'),[maximum]);self.assertEqual(self.ids(min_price='0',max_price='1000000000'),[maximum,middle,zero,self.item.id]);self.assertEqual(self.ids(category_id='3'),[])
 def test_all_filters_and_keyword_visibility_counts_and_pagination(self):
  first=self.add('10');second=self.add('10');self.add('11');self.add('10',category=1);self.add('10',condition='used')
  for state in ['pending','sold','rejected','removed']:self.add('10',state=state)
  with self.database.session() as s:
   owner=User(email='hidden@sdu.edu.kz',password_hash='PRIVATE',verified=True,suspended=True);s.add(owner);s.flush();owner_id=owner.id
  self.add('10',owner=owner_id)
  query={'q':'needle','category_id':'2','condition':'new','min_price':'10','max_price':'10','limit':'1'}
  result=self.feed(**query).json();self.assertEqual((result['total'],result['count']),(2,1));self.assertEqual(result['items'][0]['id'],second);self.assertEqual(self.ids(**query,offset='1'),[first]);self.assertEqual(self.feed(**query,offset='2').json()['items'],[]);self.assertEqual(self.feed(**query,offset='2').json()['total'],2)
  self.assertEqual(set(result['items'][0]),{'id','title','price','currency','category_id','condition','published_at','main_photo'})
  self.assertEqual(self.ids(**{**query,'q':'no match'}),[])
 def test_categories_conditions_decimal_syntax_ranges_and_duplicates(self):
  for category in ['','0','6','01','-1','+1','1.0','1e0','true',' 1','9'*5000]:
   self.assertEqual(self.feed(category_id=category).status_code,422)
  for condition in ['','New','USED','true',' new','old']:self.assertEqual(self.feed(condition=condition).status_code,422)
  bad=['','true','false','NaN','Infinity','1e2','+1','-0','-1',' 1','1 ','01','1.','.5','1,00','1.001','1000000000.01','9'*5000]
  for key in ['min_price','max_price']:
   for value in bad:
    with self.subTest(key=key,value=value[:40]):
     result=self.feed(**{key:value});self.assertEqual(result.status_code,422);self.assertEqual(result.json(),{'detail':'Invalid marketplace query.'})
  self.assertEqual(self.feed(min_price='2',max_price='1').status_code,422)
  for key,value in [('category_id','1'),('condition','new'),('min_price','0'),('max_price','1')]:
   result=self.client.get(f'/listings?{key}={value}&{key}={value}',headers=self.buyer_headers);self.assertEqual(result.status_code,422)
  self.assertEqual(self.feed(owner_id='1').status_code,422);self.assertEqual(self.feed(sort='price').status_code,422)
 def test_omitted_filters_and_protected_main_photo_contract(self):
  result=self.feed().json();self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['main_photo']['url'],f'/listings/{self.item.id}/photos/{self.photo.id}')
  self.assertEqual(self.feed(category_id='1',condition='used',min_price='12.34',max_price='12.34').json(),result)
