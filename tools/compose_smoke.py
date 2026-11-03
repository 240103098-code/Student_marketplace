"""Real owned Compose verification, never cloud deployment or user data access."""
import base64
from http.cookiejar import CookieJar
import json
import os
import re
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

from tools.container_smoke import avatar_payload
from tools.e2e_stack import borrowed_image


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));return probe.getsockname()[1]


def main():
    owner=os.environ.get('MARKETPLACE_TEST_IMAGE_OWNER','')
    suffix=owner.split('-')[1][:12] if re.fullmatch(r'marketplace92-[a-f0-9]{20}',owner) else uuid.uuid4().hex[:12]
    project='marketplace59-'+suffix;failure_project=project+'-failure';image=project+':local'
    record={'result':'FAIL','mode':'real-docker-compose-postgresql','commit':os.environ.get('GITHUB_SHA','local'),'checks':[]}
    port=free_port();origin=f'http://127.0.0.1:{port}'
    environment=dict(os.environ,POSTGRES_DB='marketplace',POSTGRES_USER='marketplace',POSTGRES_PASSWORD=secrets.token_urlsafe(32),JWT_SECRET_KEY=secrets.token_urlsafe(48),FRONTEND_ORIGINS=json.dumps([origin]),APP_PORT=str(port),APP_ENV='development',REFRESH_COOKIE_SECURE='false',MARKETPLACE_IMAGE=image)
    environment['DATABASE_URL']='postgresql+psycopg://marketplace:'+environment['POSTGRES_PASSWORD']+'@db:5432/marketplace'
    for key in list(environment):
        if key.startswith('SMTP_'):environment.pop(key)
    def command(*args,input=None,env=None,allow_failure=False):
        result=subprocess.run(args,input=input,text=True,capture_output=True,timeout=600,env=environment if env is None else env)
        if result.returncode and not allow_failure:raise RuntimeError('Owned Compose operation failed')
        return result if allow_failure else result.stdout.strip()
    def compose(*args,selected=project,override=None,env=None,allow_failure=False):
        command_args=['docker','compose','--env-file',os.devnull,'-p',selected,'-f','compose.yaml']
        if override:command_args+=['-f',str(override)]
        return command(*command_args,*args,env=env,allow_failure=allow_failure)
    def checked(name):record['checks'].append(name)
    def container(service,selected=project):return compose('ps','--all','--quiet',service,selected=selected)
    def inspect(service,format,selected=project):return command('docker','inspect',container(service,selected),'--format',format)
    def request(path,*,data=None,headers=None,method=None,opener=None):
        payload=json.dumps(data).encode() if isinstance(data,dict) else data
        actual_headers=({'Content-Type':'application/json'} if isinstance(data,dict) else {})|dict(headers or {})
        req=urllib.request.Request(origin+path,data=payload,method=method,headers=actual_headers)
        try:return (opener.open if opener else urllib.request.urlopen)(req,timeout=6)
        except urllib.error.HTTPError as result:return result
    def wait_ready():
        end=time.monotonic()+120
        while time.monotonic()<end:
            try:
                if request('/health/ready').status==200:return
            except (OSError,urllib.error.URLError):pass
            time.sleep(1)
        raise RuntimeError('Owned Compose readiness timed out')
    def sql(statement):
        return compose('exec','-T','db','psql','-U','marketplace','-d','marketplace','-At','-c',statement)
    try:
        record['docker']=command('docker','version','--format','{{.Server.Version}}')
        record['compose']=command('docker','compose','version','--short')
        for key in ('JWT_SECRET_KEY','POSTGRES_PASSWORD','DATABASE_URL'):
            missing=dict(environment);missing.pop(key)
            assert compose('config','--quiet',env=missing,allow_failure=True).returncode!=0
        checked('missing required database/JWT secrets refuse before resource creation')
        shared=borrowed_image(environment)
        if shared:
            image=shared;environment['MARKETPLACE_IMAGE']=shared
        else:compose('build','app')
        record['image_borrowed']=bool(shared)
        assert set(compose('config','--services').splitlines())=={'app','db','migrate','uploads-init'}
        record['services']=['app','db','migrate','uploads-init']
        record['application_image_id']=command('docker','image','inspect',image,'--format','{{.Id}}')
        compose('up','--detach')
        wait_ready()
        assert inspect('app','{{.Config.User}}')=='10001:10001'
        assert inspect('migrate','{{.State.ExitCode}}')=='0'
        assert inspect('uploads-init','{{.State.ExitCode}}')=='0'
        assert json.loads(inspect('db','{{json .HostConfig.PortBindings}}')) in ({},None)
        assert '/var/lib/postgresql' in [item['Destination'] for item in json.loads(inspect('db','{{json .Mounts}}'))]
        assert sql("SELECT (SELECT count(*) FROM users),(SELECT count(*) FROM email_codes),(SELECT count(*) FROM refresh_sessions),(SELECT count(*) FROM listings),(SELECT count(*) FROM listing_photos),(SELECT count(*) FROM listing_reports),(SELECT count(*) FROM categories)")=='0|0|0|0|0|0|5'
        record['postgresql']=sql('SHOW server_version')
        record['runtime']=json.loads(compose('exec','-T','app','python','-c','import sys,json,uvicorn,psycopg; print(json.dumps(dict(python=sys.version.split()[0],uvicorn=uvicorn.__version__,psycopg=psycopg.__version__)))'))
        assert request('/').status==200
        assert request('/api/auth/me').status==401
        checked('fresh gated PG18 migration and non-root real static/API with zero demo users and no public DB port')
        sql("UPDATE alembic_version SET version_num='unprepared'")
        assert request('/health/ready').status==503 and request('/health/live').status==200
        sql("UPDATE alembic_version SET version_num='0003_listings'");wait_ready()
        checked('readiness refuses unprepared migration head while liveness responds')
        password=secrets.token_urlsafe(24)
        seed="from backend.config import load_settings; from backend.database import Database; from backend.models import User; from argon2 import PasswordHasher; import sys; db=Database(load_settings());\nwith db.session() as s: s.add(User(email='container-test@sdu.edu.kz',password_hash=PasswordHasher().hash(sys.stdin.read()),verified=True,phone='+77001234567'))\ndb.dispose()"
        command('docker','exec','--interactive',container('app'),'python','-c',seed,input=password)
        cookies=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        response=request('/api/auth/login',data={'email':'container-test@sdu.edu.kz','password':password},opener=cookies)
        assert response.status==200
        token=json.load(response)['access_token'];auth={'Authorization':'Bearer '+token}
        photo=base64.b64decode(compose('exec','-T','app','python','-c',"from PIL import Image; import io,base64; b=io.BytesIO(); Image.new('RGB',(8,8)).save(b,format='PNG'); print(base64.b64encode(b.getvalue()).decode())"))
        payload,content_type=avatar_payload(photo)
        assert request('/api/users/me/avatar',data=payload,headers=auth|{'Content-Type':content_type}).status==200
        original=request('/api/users/me/avatar',headers=auth).read()
        created=request('/api/listings',data={'category_id':1,'title':'Compose persistence item','description':'Owned disposable Compose verification.','price':'12000.00','condition':'used'},headers=auth)
        assert created.status==201
        listing=json.load(created)['id']
        uploaded=request(f'/api/listings/{listing}/photos',data=payload,headers=auth|{'Content-Type':content_type})
        assert uploaded.status==201
        photo_id=json.load(uploaded)['id'];photo_path=f'/api/listings/{listing}/photos/{photo_id}'
        listing_bytes=request(photo_path,headers=auth).read()
        # Fixture-only publication, not a bypass or startup seed in Compose.
        publish="from backend.config import load_settings; from backend.database import Database; from backend.models import Listing; from backend.email_codes import utc_now; import sys; db=Database(load_settings());\nwith db.session() as s: item=s.get(Listing,int(sys.stdin.read())); item.status='active'; item.published_at=utc_now()\ndb.dispose()"
        command('docker','exec','--interactive',container('app'),'python','-c',publish,input=str(listing))
        def persisted():
            assert request('/api/auth/me',headers=auth).status==200
            assert request('/api/users/me/avatar',headers=auth).read()==original
            assert request(photo_path,headers=auth).read()==listing_bytes
            assert request('/api/users/me/avatar').status==401
            assert request(photo_path).status==401
            csrf=json.load(request('/api/auth/csrf',opener=cookies))['csrf_token']
            refreshed=request('/api/auth/refresh',method='POST',headers={'Origin':origin,'X-CSRF-Token':csrf},opener=cookies)
            assert refreshed.status==200
            assert json.load(request(f'/api/listings/{listing}',headers=auth))['price']=='12000.00'
        persisted()
        compose('stop','db')
        start=time.monotonic()
        assert request('/health/ready').status==503
        record['outage_readiness_seconds']=round(time.monotonic()-start,3)
        assert record['outage_readiness_seconds']<5.5 and request('/health/live').status==200
        compose('start','db');wait_ready();persisted()
        checked('bounded DB-outage readiness failure with responsive liveness and real pool/auth recovery')
        compose('up','--detach','--force-recreate','db','app');wait_ready();persisted()
        checked('replaced app and DB containers retain rows, refresh lineage and exact protected avatar/listing bytes')
        compose('down');compose('up','--detach');wait_ready();persisted()
        checked('down/up without volume deletion retains actual PG18 data and private uploads')
        assert os.environ.get('CONTAINER_PLAYWRIGHT_MODULE'),'Actual browser prerequisite required'
        record['browser']=json.loads(command('node','tools/compose_browser.cjs',input=json.dumps({'origin':origin,'password':password,'listing':listing})))
        checked('actual connected React browser sign-in, reload and private listing with zero external requests')
        failure_env=dict(environment,APP_PORT=str(free_port()))
        with tempfile.TemporaryDirectory(prefix='owned-compose59-',dir=os.environ.get('MARKETPLACE_TEST_PRIVATE_ROOT')) as temp:
            override=Path(temp)/'migration-failure.yaml'
            override.write_text('services:\n  migrate:\n    command: [python, -c, "raise SystemExit(19)"]\n')
            assert compose('up','--detach',selected=failure_project,override=override,env=failure_env,allow_failure=True).returncode!=0
            assert inspect('migrate','{{.State.ExitCode}}',selected=failure_project)=='19'
            cid=container('app',failure_project)
            assert not cid or command('docker','inspect',cid,'--format','{{.State.Running}}')=='false'
        checked('failed one-shot migration prevents fresh application start')
        record['result']='PASS'
    finally:
        cleanup=[]
        for selected in (project,failure_project):
            for kind,args in [('container',['docker','ps','-aq']),('volume',['docker','volume','ls','-q']),('network',['docker','network','ls','-q'])]:
                for identity in command(*args,'--filter','label=com.docker.compose.project='+selected).split():
                    template='{{index .Config.Labels "com.docker.compose.project"}}' if kind=='container' else '{{index .Labels "com.docker.compose.project"}}'
                    prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
                    assert command(*prefix,identity,'--format',template)==selected
            compose('down','--volumes','--remove-orphans','--timeout','15',selected=selected,allow_failure=True)
            containers=command('docker','ps','--all','--quiet','--filter','label=com.docker.compose.project='+selected)
            volumes=command('docker','volume','ls','--quiet','--filter','label=com.docker.compose.project='+selected)
            networks=command('docker','network','ls','--quiet','--filter','label=com.docker.compose.project='+selected)
            cleanup.append(not containers and not volumes and not networks)
        if image==project+':local':
            command('docker','image','rm',image,allow_failure=True)
            record['owned_image_absent']=command('docker','image','inspect',image,allow_failure=True).returncode!=0
            image_cleanup=record['owned_image_absent']
        else:
            record['borrowed_image_preserved']=borrowed_image(environment)==image
            image_cleanup=record['borrowed_image_preserved']
        record['owned_containers_volumes_and_networks_absent']=all(cleanup)
        complete=all(cleanup) and image_cleanup
        if not complete:record['result']='FAIL'
        Path('compose-verification.json').write_text(json.dumps(record,indent=2)+'\n')
        if not complete:raise RuntimeError('Owned Compose cleanup incomplete')


if __name__=='__main__':main()
