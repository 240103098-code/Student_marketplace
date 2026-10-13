from datetime import timedelta
from urllib.parse import urlencode
import unittest
from sqlalchemy import select,func
import test_sold_integration as fixture
from backend.models import Listing,User

class SearchPostgreSQLTest(unittest.TestCase):
 setUpClass=classmethod(fixture.SoldPostgreSQLTest.setUpClass.__func__)
 setUp=fixture.SoldPostgreSQLTest.setUp
 tearDown=fixture.SoldPostgreSQLTest.tearDown
 login=fixture.SoldPostgreSQLTest.login
 def search(self,q=None,**paging):
  if q is not None:paging['q']=q
  return self.client.get('/listings?'+urlencode(paging),headers=self.buyer_headers)
 def add(self,title,description='A useful description.',state='active',owner=None,published=None):
  with self.database.session() as s:
   row=Listing(owner_id=owner or self.owner.id,category_id=1,title=title,description=description,price=self.item.price,condition='used',status=state,published_at=(published or self.now) if state in ['active','sold'] else None,rejection_reason='Private reason' if state=='rejected' else None);s.add(row);s.flush();return row.id
 def ids(self,q=None,**paging):return [row['id'] for row in self.search(q,**paging).json()['items']]
 def test_title_description_case_unicode_trim_and_blank(self):
  title=self.add('A CAMERA offer');description=self.add('Unrelated title','The camera is barely used.');unicode=self.add('Қазақ кітабы','Русский учебник для студента.');self.add('Other item')
  self.assertEqual(set(self.ids(' camera ')),{title,description});self.assertEqual(self.ids('Қазақ'),[unicode]);self.assertEqual(self.ids('учебник'),[unicode])
  for stored,query in [('Қазақ','ҚАЗАҚ'),('учебник','УЧЕБНИК')]:
   with self.database.session() as s:folds=s.scalar(select(func.lower(stored)==func.lower(query)))
   self.assertEqual(self.ids(query),[unicode] if folds else [])
  for blank in ['', '   ', '\u2003']:
   self.assertEqual(self.search(blank).json(),self.search().json())
  self.assertEqual(self.search('nonexistent').json(),{'items':[],'total':0,'count':0,'limit':20,'offset':0})
 def test_literal_percent_underscore_escape_and_sql_looking_text(self):
  terms=['50%','_','!','\\',"' OR 1=1 --"]
  ids=[self.add('Literal '+term+' item') for term in terms];self.add('50 discount ordinary item')
  for term,id in zip(terms,ids):
   with self.subTest(term=term):self.assertEqual(self.ids(term),[id])
  self.assertEqual(self.ids("'; DROP TABLE listings; --"),[])
  with self.database.session() as s:self.assertGreater(len(list(s.scalars(select(Listing)))),0)
 def test_decoded_boundary_controls_duplicate_unknown_safe_errors(self):
  accepted=self.search('x'*200);self.assertEqual(accepted.status_code,200);self.assertEqual(accepted.json()['total'],0)
  self.assertEqual(self.search(' '+ 'x'*200).status_code,422)
  for q in ['x'*201,'hello\nworld','hello\x00world','hello\x7fworld','hello\x85world']:
   result=self.search(q);self.assertEqual(result.status_code,422);self.assertEqual(result.json(),{'detail':'Invalid marketplace query.'});self.assertNotIn(q,result.text)
  for query in ['q=book&q=other','q=book&owner_id=1','q=book&sort=title','q=book&category_id=1']:
   result=self.client.get('/listings?'+query,headers=self.buyer_headers);self.assertEqual(result.status_code,422)
 def test_filtered_totals_publication_ties_pages_and_private_visibility(self):
  for state in ['pending','sold','rejected','removed']:self.add('Matching needle '+state,state=state)
  with self.database.session() as s:
   seller=User(email='hidden@sdu.edu.kz',password_hash='PRIVATE',verified=False);s.add(seller);s.flush();seller_id=seller.id
  self.add('Matching needle hidden',owner=seller_id)
  older=self.add('Matching needle older',published=self.now-timedelta(days=1));tie1=self.add('Matching needle tie one');tie2=self.add('Matching needle tie two');newer=self.add('Matching needle newest',published=self.now+timedelta(seconds=1));self.add('Unrelated item')
  result=self.search('needle',limit=2).json();self.assertEqual([row['id'] for row in result['items']],[newer,tie2]);self.assertEqual((result['total'],result['count']),(4,2));self.assertEqual(self.ids('needle',limit=2,offset=2),[tie1,older]);self.assertEqual(self.search('needle',offset=4).json()['total'],4);self.assertEqual(self.ids('needle',offset=4),[])
  self.assertEqual(set(result['items'][0]),{'id','title','price','currency','category_id','condition','published_at','main_photo'})
 def test_searched_card_photo_remains_protected_and_description_private(self):
  result=self.search('textbook').json();self.assertEqual(result['total'],1);card=result['items'][0];self.assertEqual(card['id'],self.item.id);self.assertNotIn('description',card);self.assertEqual(card['main_photo']['url'],f'/listings/{self.item.id}/photos/{self.photo.id}')
  self.assertEqual(self.client.get(card['main_photo']['url']).status_code,401);self.assertEqual(self.client.get(card['main_photo']['url'],headers=self.buyer_headers).status_code,200)
