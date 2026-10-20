import json
import unittest
from unittest.mock import patch
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from backend.app import create_app
from backend.config import Settings
from tools.export_openapi import schema,rendered
from contract_support import validate_json,assert_response

class CanonicalOpenApiTest(unittest.TestCase):
 def app(self):return create_app(Settings(APP_ENV='test',DATABASE_URL='postgresql+psycopg://schema_only@127.0.0.1/schema_only',JWT_SECRET_KEY='contract-only-'+'x'*48),database=object(),sender=object())
 def test_all_actual_routes_have_success_schemas_safe_errors_and_resolving_refs(self):
  app=self.app();document=app.openapi()
  actual={(route.path,method.lower()) for route in iter_route_contexts(app.routes) if getattr(route,'include_in_schema',False) for method in route.methods}
  declared={(path,method) for path,row in document['paths'].items() for method in row}
  self.assertEqual(actual,declared)
  self.assertNotIn('/mock/reset',document['paths'])
  for component in document['components']['schemas'].values():Draft202012Validator.check_schema(component)
  def walk(node):
   if isinstance(node,dict):
    if '$ref' in node:
     self.assertTrue(node['$ref'].startswith('#/components/schemas/'));self.assertIn(node['$ref'].split('/')[-1],document['components']['schemas'])
    for child in node.values():walk(child)
   elif isinstance(node,list):
    for child in node:walk(child)
  walk(document)
  for path,method in actual:
   operation=document['paths'][path][method]
   self.assertTrue(operation['x-contract-source'])
   for status,response in operation['responses'].items():
    if status=='204':self.assertNotIn('content',response)
    else:
     self.assertTrue(response['content'])
     for media,content in response['content'].items():self.assertTrue(content['schema'])
    if int(status)>=400:self.assertEqual(response['content']['application/json']['schema'],{'$ref':'#/components/schemas/SafeError'})
   if not path.startswith('/auth/') or path in ['/auth/me','/auth/change-password']:self.assertEqual(operation['security'],[{'HTTPBearer':[]}])
  self.assertNotIn('422',document['paths']['/auth/logout']['post']['responses'])
  # Recovery SMTP failures remain generic202 (real HTTP tests); SQLite writer
  # exhaustion independently returns the new bounded, sanitized busy503.
  self.assertIn('Bounded SQLite writer wait exhausted',document['paths']['/auth/forgot-password']['post']['responses']['503']['description'])
  self.assertIn('Recovery SMTP delivery failures still return generic 202',document['paths']['/auth/forgot-password']['post']['responses']['503']['description'])
 def test_strict_manual_schema_matches_wire_rules_and_partial_null_semantics(self):
  document=schema();components=document['components']['schemas']
  for path in ['/listings','/listings/mine','/admin/users','/admin/listings','/admin/reports']:
   operation=document['paths'][path]['get'];parameters={p['name']:p for p in operation['parameters']}
   self.assertEqual(parameters['limit']['schema']['maximum'],50);self.assertEqual(parameters['offset']['schema']['maximum'],9223372036854775807);self.assertEqual(operation['x-strict-query']['duplicate'],'rejected')
  create=components['ListingCreateRequest'];valid={'title':'Synthetic item','description':'Synthetic detailed item.','category_id':3,'condition':'used','price':'10.23000'}
  validate_json(document,create,valid)
  for value in ['10.231','1e3',' 10.00','1000000000.01',None,True]:
   with self.subTest(value=value):
    with self.assertRaises(Exception):validate_json(document,create,{**valid,'price':value})
  for value in [{},{'name':None},{'phone':'1234'},{'role':'admin'}]:
   with self.assertRaises(Exception):validate_json(document,components['ProfilePatch'],value)
  validate_json(document,components['ProfilePatch'],{'phone':None})
  validate_json(document,components['ProfilePatch'],{'name':'Synthetic name'})
  from backend.profile_schemas import ProfilePatch
  contact={'external_contact_url':'HTTPS://example.invalid/contract'}
  self.assertEqual(ProfilePatch.model_validate(contact).external_contact_url,contact['external_contact_url'])
  validate_json(document,components['ProfilePatch'],contact)
  with self.assertRaises(Exception):validate_json(document,components['ListingEditRequest'],{'description':None})
  with self.assertRaises(Exception):validate_json(document,components['EmptyAction'],{'status':'active'})
  self.assertEqual(document['paths']['/listings/{listing_id}/photos']['post']['requestBody']['content']['multipart/form-data']['schema']['required'],['image'])
 def test_actual_safe_errors_csrf_logout_and_rate_headers_validate_without_services(self):
  app=self.app();document=app.openapi()
  with TestClient(app) as client:
   for method,path,kwargs,status in [('post','/auth/register',{'json':{'email':'bad','password':'PRIVATE_INPUT'}},422),('post','/auth/login',{'json':{'email':'demo@sdu.edu.kz','password':'synthetic-password'},'headers':{'Origin':'https://untrusted.invalid'}},403),('get','/auth/csrf',{},401),('post','/auth/logout',{'headers':{'Origin':'http://localhost:5173','X-CSRF-Token':'a'*64}},204),('get','/listings',{},401),('post','/auth/login',{'content':b'x'*65537},413)]:
    with self.subTest(path=path,status=status):
     response=getattr(client,method)(path,**kwargs);assert_response(self,document,path,method,response,status);self.assertNotIn('PRIVATE_INPUT',response.text)
   self.assertEqual(client.get('/auth/csrf').headers['www-authenticate'],'Bearer')
   from backend.abuse import Limiter
   app.state.limiter=Limiter(app.state.clock)
   for _ in range(11):response=client.post('/auth/register',json={'email':'bad'})
   assert_response(self,document,'/auth/register','post',response,429);self.assertGreater(int(response.headers['retry-after']),0)
 def test_actual_app_openapi_endpoint_export_and_drift_without_startup_or_environment(self):
  with patch.dict('os.environ',{'DATABASE_URL':'PRIVATE_SENTINEL','JWT_SECRET_KEY':'PRIVATE_SENTINEL'}):
   document=self.app().openapi();self.assertNotIn('PRIVATE_SENTINEL',json.dumps(document));self.assertEqual(document,schema())
  app=self.app()
  @app.get('/contract-drift-probe')
  def probe():return {'probe':True}
  self.assertNotEqual(json.dumps(app.openapi(),sort_keys=True),json.dumps(schema(),sort_keys=True))
  with TestClient(self.app()) as client:self.assertEqual(client.get('/openapi.json').json(),schema())
