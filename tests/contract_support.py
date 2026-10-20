"""Standards-based assertions against the actual app's OpenAPI, no auth bypass."""
from jsonschema import Draft202012Validator,FormatChecker

def validate_json(document,schema,value):
    validator=Draft202012Validator({**schema,'components':document['components']},format_checker=FormatChecker())
    validator.validate(value)

def assert_response(test,document,path,method,response,status=None):
    if status is not None:test.assertEqual(response.status_code,status)
    operation=document['paths'][path][method]
    contract=operation['responses'][str(response.status_code)]
    test.assertEqual(response.headers.get('cache-control'),'private, no-store')
    test.assertEqual(response.headers.get('x-content-type-options'),'nosniff')
    if response.status_code==204:test.assertEqual(response.content,b'');return
    media=response.headers.get('content-type','').split(';',1)[0]
    test.assertIn(media,contract['content'])
    if media=='application/json':validate_json(document,contract['content'][media]['schema'],response.json())
    else:test.assertGreater(len(response.content),0)
