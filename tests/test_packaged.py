"""Packaged routing exercises the real application, including cookie/CSRF guards."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import io
from PIL import Image
from tools.container_smoke import avatar_payload

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import load_settings
from backend.models import User
from argon2 import PasswordHasher
from backend.packaged import PackagedApp


class PackagedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'assets').mkdir()
        (root / 'index.html').write_text('<html>real frontend</html>')
        (root / 'assets' / 'app.js').write_text('export const real=true;')
        api = create_app(load_settings(environ={'JWT_SECRET_KEY':'TEST_ONLY_'+'x'*50,'APP_ENV':'test','DATABASE_URL':'sqlite+pysqlite:///:memory:','FRONTEND_ORIGINS':'["http://127.0.0.1"]'},env_file=None))
        api.root_path='/api'
        self.api=api
        self.client=TestClient(PackagedApp(api,root),base_url="http://127.0.0.1")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__,None,None,None)

    def test_spa_assets_api_and_private_denials_remain_distinct(self):
        for path in ['/', '/login','/listings/1','/admin/listings/1']:
            self.assertIn('text/html',self.client.get(path).headers['content-type'])
        asset=self.client.get('/assets/app.js')
        self.assertEqual(asset.status_code,200)
        self.assertIn('javascript',asset.headers['content-type'])
        for path in ['/api/unknown','/api/assets/app.js','/uploads/a.jpg','/.env','/assets/missing.js']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,404,path)
            self.assertNotIn('text/html',response.headers['content-type'])
        for path in ['/api/listings','/api/listings/1/photos/1','/api/users/me/avatar']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,401,path)
            self.assertIn('application/json',response.headers['content-type'])
        self.assertEqual(self.client.get('/api/openapi.json').status_code,200)
        self.assertIn('/api/openapi.json',self.client.get('/api/docs').text)
        self.assertEqual(self.client.post('/login').status_code,404)

    def test_cookie_path_refresh_origin_csrf_and_logout(self):
        with self.api.state.database.session() as session:
            session.add(User(email='packaged@sdu.edu.kz',password_hash=PasswordHasher().hash('SYNTHETIC_PASSWORD_123'),verified=True))
        response=self.client.post('/api/auth/login',json={'email':'packaged@sdu.edu.kz','password':'SYNTHETIC_PASSWORD_123'},headers={'Origin':'http://127.0.0.1'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('Path=/api/auth',response.headers['set-cookie'])
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        auth={'Authorization':'Bearer '+response.json()['access_token']}
        image=io.BytesIO()
        Image.new('RGB',(8,8)).save(image,format='PNG')
        body, content_type=avatar_payload(image.getvalue())
        uploaded=self.client.post('/api/users/me/avatar',content=body,headers={**auth,'Content-Type':content_type})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        private=self.client.get('/api/users/me/avatar',headers=auth)
        self.assertEqual(private.status_code,200)
        self.assertIn('image/',private.headers['content-type'])
        self.assertIn('no-store',private.headers['cache-control'])
        csrf=self.client.get('/api/auth/csrf').json()['csrf_token']
        self.assertEqual(self.client.post('/api/auth/refresh',headers={'Origin':'http://evil.invalid','X-CSRF-Token':csrf}).status_code,403)
        refreshed=self.client.post('/api/auth/refresh',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':csrf})
        self.assertEqual(refreshed.status_code,200,refreshed.text)
        csrf=self.client.get('/api/auth/csrf').json()['csrf_token']
        logged_out=self.client.post('/api/auth/logout',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':csrf})
        self.assertEqual(logged_out.status_code,204)
        self.assertIn('Path=/api/auth',logged_out.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/auth/me',headers={'Authorization':'Bearer '+refreshed.json()['access_token']}).status_code,401)

    def test_minimal_health_routes_do_not_change_standalone_contract(self):
        from unittest.mock import AsyncMock,patch
        self.assertEqual(self.client.get('/health/live').json(),{'status':'ok'})
        response=self.client.get('/health/ready')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'status':'not-ready'})
        self.assertIn('no-store',response.headers['cache-control'])
        with patch.object(self.client.app.readiness,'ready',new=AsyncMock(return_value=True)):
            self.assertEqual(self.client.get('/health/ready').status_code,200)
        self.assertEqual(self.client.post('/health/live').status_code,404)
        self.assertNotIn('/health/live',self.client.get('/api/openapi.json').json()['paths'])

