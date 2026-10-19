import json
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import Settings
from backend.listing_schemas import BrowseListingsPage, ListingCreateRequest, ListingPhotoSummary
from tools.export_openapi import ROOT, schema, rendered

class OpenApiContractTest(unittest.TestCase):
    def test_export_is_deterministic_actual_app_without_services_or_environment(self):
        with patch('backend.database.Database',side_effect=AssertionError('No engine allowed')), patch('backend.mail.SmtpSender',side_effect=AssertionError('No mail allowed')):
            self.assertEqual(rendered(),(ROOT/'openapi.yml').read_text(encoding='utf-8'))
            self.assertEqual(rendered(),rendered())
        paths=schema()['paths']
        self.assertIn('/auth/refresh',paths)
        self.assertIn('/listings/{listing_id}/photos',paths)
        self.assertIn('/admin/listings/{listing_id}/approve',paths)
        self.assertEqual(paths['/listings']['get']['responses']['200']['content']['application/json']['schema']['$ref'],'#/components/schemas/BrowseListingsPage')
        request=paths['/listings']['post']['requestBody']['content']['application/json']['schema']
        self.assertEqual(set(request['required']),{'title','description','price','category_id','condition'})

    def test_actual_http_validation_security_and_safe_error_contract_without_dependency_bypass(self):
        settings=Settings(APP_ENV='test',DATABASE_URL='postgresql+psycopg://schema_only@127.0.0.1/schema_only',JWT_SECRET_KEY='contract-only-'+'x'*48)
        app=create_app(settings,database=object(),sender=object())
        with TestClient(app) as client:
            response=client.post('/auth/register',json={'email':'not-valid','password':'PRIVATE_INPUT'})
            self.assertEqual(response.status_code,422)
            self.assertEqual(set(response.json()),{'detail'})
            self.assertNotIn('PRIVATE_INPUT',response.text)
            self.assertEqual(client.get('/listings').status_code,401)
            self.assertEqual(client.get('/admin/me').status_code,401)
            self.assertEqual(client.get('/listings/1/photos/1').status_code,401)

    def test_canonical_synthetic_examples_validate_against_actual_server_models(self):
        data=json.loads((ROOT/'_docs/evidence/integration-contracts/canonical-examples.json').read_text())
        BrowseListingsPage.model_validate(data['catalog'])
        ListingCreateRequest.model_validate(data['create_request'])
        ListingPhotoSummary.model_validate(data['photo'])
        self.assertEqual(data['catalog']['items'][0]['price'],'38000.00')
        self.assertEqual(data['photo']['url'],'/listings/1/photos/1')
