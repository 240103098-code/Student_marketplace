"""Owned Docker-only verification; no provider, registry publication or real mail."""
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid


def avatar_payload(photo):
    boundary='owned-container-photo'
    payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+photo+f'\r\n--{boundary}--\r\n'.encode())
    return payload, 'multipart/form-data; boundary='+boundary


def main():
    suffix = uuid.uuid4().hex[:12]
    image, container, volume = (f"marketplace-57-{suffix}{tail}" for tail in ("-image", "-app", "-data"))
    record = {"result":"FAIL", "commit":os.environ.get("GITHUB_SHA", "local"), "checks":[]}
    def command(*args, input=None):
        result=subprocess.run(args,input=input,text=True,capture_output=True,timeout=600)
        if result.returncode:
            # No environment, command arguments, credential-bearing response or
            # application logs are exported into the public artifact.
            raise RuntimeError("Owned container operation failed: "+args[0])
        return result.stdout.strip()
    def checked(name):
        record["checks"].append(name)
    try:
        record["docker"]=command("docker","version","--format","{{.Server.Version}}")
        command("docker","build","--tag",image,".")
        checked("actual multi-stage image build")
        record["image_id"]=command("docker","image","inspect",image,"--format","{{.Id}}")
        assert command("docker","image","inspect",image,"--format","{{.Config.User}}") == "10001:10001"
        command("docker","volume","create",volume)
        # Only the newly generated named volume is initialized, never a host path.
        command("docker","run","--rm","--user","0:0","--volume",volume+":/data",image,"chown","10001:10001","/data")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1",0)); port=probe.getsockname()[1]
        origin=f"http://127.0.0.1:{port}"
        environment={"APP_ENV":"test","DATABASE_URL":"sqlite+pysqlite:////data/marketplace.sqlite3","UPLOAD_DIR":"/data/uploads","JWT_SECRET_KEY":secrets.token_urlsafe(48),"FRONTEND_ORIGINS":json.dumps([origin])}
        # Pass names, not values, in process arguments; Docker config is disposable.
        os.environ.update(environment)
        env_args=[arg for key in environment for arg in ("--env",key)]
        common=["--volume",volume+":/data",*env_args]
        command("docker","run","--rm",*common,image,"python","-m","alembic","-c","alembic-sqlite.ini","upgrade","head")
        command("docker","run","--detach","--name",container,"--publish",f"127.0.0.1:{port}:8000",*common,image)
        mapping=command("docker","port",container,"8000/tcp")
        origin="http://"+mapping
        def request(path, *, method="GET", data=None, headers=None):
            req=urllib.request.Request(origin+path,data=data,method=method,headers=headers or {})
            try:
                return urllib.request.urlopen(req,timeout=5)
            except urllib.error.HTTPError as response:
                return response
        for _ in range(60):
            try:
                if request('/api/openapi.json').status==200:break
            except (OSError,urllib.error.URLError):pass
            time.sleep(1)
        else:raise RuntimeError("Owned image startup timed out")
        # Runtime needs the exact browser origin, including the dynamically owned port.
        command("docker","exec",container,"python","-c","import os; assert os.getuid()==10001")
        checked("non-root identity and mounted SQLite migration/start")
        root=request('/');html=root.read().decode();assert root.status==200 and '<html' in html
        import re
        asset=re.search(r'src="(/assets/[^\"]+\.js)"',html).group(1)
        js=request(asset).read().decode();assert 'localhost:8000' not in js and '127.0.0.1:8000' not in js
        for marker in ('student-demo@sdu.edu.kz','SYNTHETIC DEMO','mockService','Graphing calculator, works perfectly'):assert marker not in js
        for path in ('/login','/listings/1'):
            response=request(path);assert response.status==200 and 'text/html' in response.headers['Content-Type']
        for path,status in (('/api/listings',401),('/api/users/me/avatar',401),('/api/listings/1/photos/1',401),('/api/unknown',404),('/uploads/private.jpg',404),('/.env',404)):
            response=request(path);assert response.status==status and 'application/json' in response.headers['Content-Type']
        checked("real SPA/assets/API prefix/private denials and API-not-HTML 404")
        command("docker","exec",container,"python","-c","from pathlib import Path; p=Path('/app'); assert not any(p.rglob('.env*')); assert not (p/'tools').exists(); assert not (p/'tests').exists(); assert not (p/'frontend').exists(); assert not any(p.rglob('*.jpg')); assert not (p/'.git').exists()")
        history=command("docker","history","--no-trunc",image)
        assert environment["JWT_SECRET_KEY"] not in history
        record["runtime"]=json.loads(command("docker","exec",container,"python","-c","import sys,sqlite3,json,uvicorn; print(json.dumps(dict(python=sys.version.split()[0],sqlite=sqlite3.sqlite_version,uvicorn=uvicorn.__version__)))"))
        checked("runtime file/layer and real-bundle secret/mock exclusion")
        password=secrets.token_urlsafe(24)
        seed="from backend.config import load_settings; from backend.database import Database; from backend.models import User; from argon2 import PasswordHasher; import sys; db=Database(load_settings());\nwith db.session() as s: s.add(User(email='container-test@sdu.edu.kz',password_hash=PasswordHasher().hash(sys.stdin.read()),verified=True))\ndb.dispose()"
        command("docker","exec","--interactive",container,"python","-c",seed,input=password)
        response=request('/api/auth/login',method='POST',data=json.dumps({'email':'container-test@sdu.edu.kz','password':password}).encode(),headers={'Content-Type':'application/json'})
        assert response.status==200
        token=json.load(response)['access_token'];auth={'Authorization':'Bearer '+token}
        assert request('/api/auth/me',headers=auth).status==200
        # Actual private image upload and read; Pillow is an existing runtime dependency.
        photo=command("docker","exec",container,"python","-c","from PIL import Image; import io,base64; b=io.BytesIO(); Image.new('RGB',(8,8)).save(b,format='PNG'); print(base64.b64encode(b.getvalue()).decode())")
        payload, content_type=avatar_payload(base64.b64decode(photo))
        assert request('/api/users/me/avatar',method='POST',data=payload,headers={**auth,'Content-Type':content_type}).status==200
        original=request('/api/users/me/avatar',headers=auth).read()
        if os.environ.get('CONTAINER_PLAYWRIGHT_MODULE'):
            record['browser']=json.loads(command('node','tools/container_browser.cjs',input=json.dumps({'origin':origin,'password':password})))
            checked("actual packaged browser sign-in, navigation and reload")
        command("docker","stop","--time","15",container)
        assert command("docker","inspect",container,"--format","{{.State.ExitCode}}")=='0'
        command("docker","start",container)
        for _ in range(30):
            try:
                if request('/api/auth/me',headers=auth).status==200:break
            except (OSError,urllib.error.URLError):pass
            time.sleep(1)
        else:raise RuntimeError('Restart authentication failed')
        assert request('/api/users/me/avatar',headers=auth).read()==original
        checked("graceful signal exit zero; mounted account/session/private image survive restart")
        record['result']='PASS'
    finally:
        subprocess.run(['docker','rm','--force',container],capture_output=True,timeout=30)
        subprocess.run(['docker','volume','rm',volume],capture_output=True,timeout=30)
        subprocess.run(['docker','image','rm',image],capture_output=True,timeout=30)
        record['owned_container_absent']=subprocess.run(['docker','inspect',container],capture_output=True).returncode!=0
        record['owned_volume_absent']=subprocess.run(['docker','volume','inspect',volume],capture_output=True).returncode!=0
        if not (record['owned_container_absent'] and record['owned_volume_absent']):
            record['result']='FAIL'
        Path('container-verification.json').write_text(json.dumps(record,indent=2)+'\n')
        if not (record['owned_container_absent'] and record['owned_volume_absent']):
            raise RuntimeError('Owned Docker cleanup did not complete')


if __name__=='__main__':main()
