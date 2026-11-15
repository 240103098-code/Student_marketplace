"""Opt-in Linux-only synthetic isolation/capacity rehearsal. Native output stays private.

No .env is loaded; no host/cloud/SSH credentials are accepted. Docker administrators
are outside the isolation boundary. Reports contain only explicitly constructed fields.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'marketplace.rehearsal101.owner'
CAPS = {'app':(.50,256), 'db':(.50,384), 'migrate':(.50,256),
        'uploads-init':(.25,64), 'smtp':(.15,96), 'proxy':(.25,96),
        'collector':(.50,192), 'prometheus':(.75,384), 'grafana':(.50,256)}
PHASES = (('baseline',120), ('idle',120), ('load',300), ('outage',60), ('recovery',120))


class Failure(Exception):
    """Only fixed public failure stage names belong here."""


def require(value, stage):
    if not value:
        raise Failure(stage)


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else 0


def digest(value):
    return hashlib.sha256(value).hexdigest()


def port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1',0))
        return connection.getsockname()[1]


def bounded(args, *, env=None, timeout=30, data=None, okay=False):
    try:
        result = subprocess.run(args,cwd=ROOT,env=env,input=data,text=True,
                                capture_output=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):
        raise Failure('bounded-subprocess') from None
    require(okay or result.returncode == 0, 'subprocess-status')
    return result


class LocalTLS(http.client.HTTPSConnection):
    """Connect loopback while keeping the requested Host, SNI and verified SAN."""
    def connect(self):
        raw = socket.create_connection(('127.0.0.1',self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw,server_hostname=self.host)


def request(origin, path, *, method='GET', body=None, headers=None, context=None):
    parsed = urllib.parse.urlsplit(origin)
    connection = (LocalTLS(parsed.hostname,parsed.port,context=context,timeout=8)
                  if parsed.scheme=='https' else
                  http.client.HTTPConnection('127.0.0.1',parsed.port,timeout=8))
    try:
        connection.request(method,path,body,headers or {})
        response=connection.getresponse()
        return response.status,dict(response.getheaders()),response.read(4*1024*1024)
    finally:
        connection.close()


def metrics(text):
    """Numeric Collector self-metrics only, with all labels discarded."""
    result={}
    for line in text.splitlines():
        if line.startswith('#'):continue
        match=re.fullmatch(r'(otelcol_[a-zA-Z0-9_]+)(?:\{[^\n]*\})?\s+([0-9.eE+\-]+)(?:\s+\d+)?',line)
        if match:
            result[match[1]]=result.get(match[1],0)+float(match[2])
    return result


def resources(service, owner):
    cpu,memory=CAPS[service]
    return {'cpus':cpu,'mem_limit':str(memory)+'m','pids_limit':128,
            'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}},
            'labels':{LABEL:owner},'restart':'no'}


class Rehearsal:
    def __init__(self):
        self.owner='marketplace101-'+uuid.uuid4().hex[:20]
        self.private=Path(tempfile.mkdtemp(prefix=self.owner+'-'))
        self.private.chmod(0o700)
        # Inherit only the ordinary local executable/runtime environment.
        self.env={key:os.environ[key] for key in ('PATH','HOME','LANG','DOCKER_HOST','DOCKER_CONTEXT','DOCKER_CONFIG','XDG_RUNTIME_DIR') if key in os.environ}
        self.image=self.owner+':local'
        self.deadline=time.monotonic()+1650
        self.projects=[]
        self.record={'result':'FAIL','mode':'actual-linux-disposable','owner':self.owner,
                     'checks':{},'phases':{},'samples':[], 'hosted_activation':'blocked-capacity-unproven',
                     'future_overhead':'Application instrumentation, trace/log storage and export unmeasured; remeasure under #103.',
                     'cleanup':False}

    def run(self,args,**kw):
        require(time.monotonic()<self.deadline,'outer-deadline')
        kw['timeout']=min(kw.get('timeout',30),max(1,self.deadline-time.monotonic()))
        okay=kw.pop('okay',False)
        result=bounded(args,env=self.env,okay=True,**kw)
        self.record['last_subprocess_exit_status']=result.returncode
        require(okay or result.returncode==0,'subprocess-status')
        return result

    def compose(self,stack,*args,**kw):
        require(re.fullmatch(re.escape(self.owner)+r'-(dev|prod|obs)',stack['project']), 'project-ownership')
        return self.run(['docker','compose','--env-file',os.devnull,'-p',stack['project'],
                         '-f',str(stack['compose']),*args],**kw)

    def check(self,name,value=True):
        self.record['checks'][name]=bool(value)
        require(value,name)

    def certificates(self):
        self.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                  '-keyout',str(self.private/'ca.key'),'-out',str(self.private/'ca.pem'),
                  '-subj','/CN=Disposable marketplace101 CA','-addext','basicConstraints=critical,CA:TRUE'])
        for name,san in [('web','DNS:dev.marketplace.test,DNS:prod.marketplace.test'),('smtp','DNS:smtp')]:
            directory=self.private/name;directory.mkdir()
            self.run(['openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',str(directory/'server.key'),
                      '-out',str(directory/'server.csr'),'-subj','/CN='+('smtp' if name=='smtp' else 'dev.marketplace.test')])
            (directory/'ext').write_text('subjectAltName='+san+'\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
            self.run(['openssl','x509','-req','-in',str(directory/'server.csr'),'-CA',str(self.private/'ca.pem'),
                      '-CAkey',str(self.private/'ca.key'),'-CAcreateserial','-days','1','-out',str(directory/'server.pem'),
                      '-extfile',str(directory/'ext')])
        self.context=ssl.create_default_context(cafile=str(self.private/'ca.pem'))

    def stack(self,name):
        project=self.owner+'-'+name
        directory=self.private/name;directory.mkdir()
        (directory/'mail').mkdir()
        for filename in ('server.key','server.pem'):
            shutil.copyfile(self.private/'smtp'/filename,directory/filename)
        password=secrets.token_hex(32)
        role='fixture_'+name
        environment={'POSTGRES_DB':'fixture_'+name,'POSTGRES_USER':role,'POSTGRES_PASSWORD':password,
                     'JWT_SECRET_KEY':secrets.token_hex(48),'APP_ENV':'production' if name=='prod' else 'development',
                     'REFRESH_COOKIE_SECURE':'true','UPLOAD_DIR':'/data/uploads','SMTP_HOST':'smtp',
                     'SMTP_PORT':'2525','SMTP_USERNAME':name,'SMTP_PASSWORD':secrets.token_hex(32),
                     'SMTP_FROM_EMAIL':'fixture@sdu.edu.kz','SMTP_SECURITY':'starttls','SSL_CERT_FILE':'/fixture-ca.pem'}
        environment['DATABASE_URL']='postgresql+psycopg://'+role+':'+password+'@db:5432/fixture_'+name
        https_port=port()
        origin='https://'+name+'.marketplace.test:'+str(https_port)
        environment['FRONTEND_ORIGINS']=json.dumps([origin])
        (directory/'smtp.json').write_text(json.dumps({'username':name,'password':environment['SMTP_PASSWORD']}))
        # Read the public Compose source only, never user .env or expanded configuration.
        # Standalone scoped composition retains its exact commands and gate dependencies.
        source=(ROOT/'compose.yaml').read_text()
        pg_image=re.search(r'image: (postgres:[^\s]+)',source)[1]
        appbase={'image':self.image,'pull_policy':'never','cap_drop':['ALL'],
                 'security_opt':['no-new-privileges:true']}
        services={
            'db':{'image':pg_image,'environment':{k:environment[k] for k in ('POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD')},
                  'volumes':['pgdata:/var/lib/postgresql'],
                  'healthcheck':{'test':['CMD-SHELL','pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],'interval':'2s','timeout':'3s','retries':30}},
            'uploads-init':dict(appbase,user='0:0',command=['python','-m','backend.compose_runtime','prepare-uploads'],
                                volumes=['uploads:/data/uploads'],cap_add=['CHOWN','FOWNER']),
            'migrate':dict(appbase,command=['python','-m','backend.compose_runtime','migrate'],environment=environment,
                           depends_on={'db':{'condition':'service_healthy'}},read_only=True),
            'smtp':{'image':self.image,'pull_policy':'never','user':'0:0','command':['python','/fixture/smtp_sink.py'],
                    'volumes':[str(directory)+':/fixture',str(ROOT/'e2e/smtp_sink.py')+':/fixture/smtp_sink.py:ro']},
            'app':dict(appbase,command=['python','-m','backend.compose_runtime','serve'],environment=environment,
                       volumes=['uploads:/data/uploads',str(self.private/'ca.pem')+':/fixture-ca.pem:ro'],read_only=True,
                       tmpfs=['/tmp:size=16777216'],depends_on={'db':{'condition':'service_healthy'},
                       'migrate':{'condition':'service_completed_successfully'},'uploads-init':{'condition':'service_completed_successfully'},
                       'smtp':{'condition':'service_started'}},healthcheck={'test':['CMD','python','-m','backend.compose_runtime','probe'],
                       'interval':'5s','timeout':'6s','retries':12,'start_period':'10s'}),
            'proxy':{'image':self.image,'pull_policy':'never','user':'0:0','command':['python','/proxy.py'],
                     'ports':['127.0.0.1:'+str(https_port)+':8443'],
                     'volumes':[str(self.private/'web')+':/tls:ro',str(ROOT/'ops/rehearsal101/proxy.py')+':/proxy.py:ro'],
                     'depends_on':{'app':{'condition':'service_healthy'}},'read_only':True,'cap_drop':['ALL']}}
        for service,config in services.items():config.update(resources(service,self.owner))
        config={'services':services,'volumes':{v:{'labels':{LABEL:self.owner}} for v in ('pgdata','uploads')},
                'networks':{'default':{'internal':True,'labels':{LABEL:self.owner}}}}
        stack={'name':name,'project':project,'directory':directory,'compose':directory/'compose.json',
               'config':config,'environment':environment,'origin':origin}
        self.save(stack);self.projects.append(stack)
        return stack

    def save(self,stack):
        stack['compose'].write_text(json.dumps(stack['config']))

    def up(self,stack):
        self.compose(stack,'up','-d','--force-recreate','--wait','--wait-timeout','120',timeout=150)

    def api(self,stack,path,*,method='GET',value=None,token=None,cookie=None,origin=None,body=None,headers=None):
        h=dict(headers or {})
        if value is not None:body=json.dumps(value).encode();h['Content-Type']='application/json'
        if token:h['Authorization']='Bearer '+token
        if cookie:h['Cookie']=cookie
        if origin:h['Origin']=origin
        return request(stack['origin'],'/api'+path,method=method,body=body,headers=h,context=self.context)

    def journey(self,stack):
        email='rehearsal-'+uuid.uuid4().hex+'@sdu.edu.kz';password=secrets.token_hex(24)
        require(self.api(stack,'/auth/register',method='POST',value={'email':email,'password':password})[0]==201,'normal-register')
        inbox=stack['directory']/'mail'/(email+'.json')
        end=time.monotonic()+15
        while not inbox.exists() and time.monotonic()<end:time.sleep(.1)
        require(inbox.exists(),'normal-smtp-delivery')
        message=json.loads(inbox.read_text());inbox.unlink()
        self.check(stack['name']+'-smtp-starttls-auth',message['tls'] and message['authenticated'])
        require(self.api(stack,'/auth/verify-email',method='POST',value={'email':email,'code':message['code']})[0]==200,'normal-verification')
        status,headers,body=self.api(stack,'/auth/login',method='POST',value={'email':email,'password':password})
        require(status==200,'normal-login')
        stack.update(email=email,password=password,token=json.loads(body)['access_token'],cookie=headers['set-cookie'].split(';')[0])
        # Generate a nonsensitive PNG with the existing locked Pillow dependency.
        from PIL import Image
        import io
        image=io.BytesIO();Image.new('RGB',(8,8),(90,160,120)).save(image,format='PNG')
        boundary=secrets.token_hex(12)
        multipart=('--'+boundary+'\r\nContent-Disposition: form-data; name="image"; filename="synthetic.png"\r\nContent-Type: image/png\r\n\r\n').encode()+image.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
        require(self.api(stack,'/users/me/avatar',method='POST',token=stack['token'],body=multipart,
                         headers={'Content-Type':'multipart/form-data; boundary='+boundary})[0]==200,'normal-upload')
        self.check(stack['name']+'-own-private-read',self.api(stack,'/users/me',token=stack['token'])[0]==200)
        self.check(stack['name']+'-anonymous-denied',all(self.api(stack,p)[0]==401 for p in ('/users/me','/users/me/avatar')))
        stack['upload_hash']=digest(self.api(stack,'/users/me/avatar',token=stack['token'])[2])

    def sql(self,stack,sql):
        return self.compose(stack,'exec','-T','db','psql','-U',stack['environment']['POSTGRES_USER'],
                            '-d',stack['environment']['POSTGRES_DB'],'-At','-c',sql).stdout.strip()

    def fingerprint(self,stack):
        # All data here is synthetic; only its aggregate hash leaves this private routine.
        dump=self.compose(stack,'exec','-T','db','pg_dump','-U',stack['environment']['POSTGRES_USER'],
                          '-d',stack['environment']['POSTGRES_DB'],'--data-only','--no-owner','--no-privileges').stdout
        # PostgreSQL dump random restrict/unrestrict tokens vary per invocation.
        stable='\n'.join(line for line in dump.splitlines() if not line.startswith(('\\restrict','\\unrestrict')))
        return {'data':digest(stable.encode()),'head':self.sql(stack,'SELECT version_num FROM alembic_version'),
                'upload':digest(self.api(stack,'/users/me/avatar',token=stack['token'])[2])}

    def preserved(self,prod,baseline,name):
        self.check(name,self.fingerprint(prod)==baseline and self.api(prod,'/users/me',token=prod['token'])[0]==200
                   and request(prod['origin'],'/health/ready',context=self.context)[0]==200)

    def failed_gate(self,stack,name,result):
        ids=self.compose(stack,'ps','-aq').stdout.split()
        info=json.loads(self.run(['docker','inspect',*ids]).stdout)
        app=[c for c in info if c['Config']['Labels']['com.docker.compose.service']=='app']
        migrate=[c for c in info if c['Config']['Labels']['com.docker.compose.service']=='migrate']
        self.check(name,result.returncode!=0 and bool(migrate) and
                   all(not c['State']['Running'] and c['State']['ExitCode']!=0 for c in migrate) and
                   all(not c['State']['Running'] for c in app))

    def inspect(self,stack):
        ids=self.compose(stack,'ps','-aq').stdout.split()
        actual=json.loads(self.run(['docker','inspect',*ids]).stdout)
        for container in actual:
            labels=container['Config']['Labels']
            require(labels.get(LABEL)==self.owner and labels.get('com.docker.compose.project')==stack['project'],'inspect-labels')
            require(all(name.startswith(stack['project']+'_') for name in container['NetworkSettings']['Networks']),'network-membership')
            for mount in container['Mounts']:
                if mount['Type']=='volume':require(mount['Name'].startswith(stack['project']+'_'),'volume-membership')
        self.check(stack['name']+'-mount-network-labels')
        self.check(stack['name']+'-db-identity',self.sql(stack,'SELECT current_database()||\':\'||current_user')==
                   stack['environment']['POSTGRES_DB']+':'+stack['environment']['POSTGRES_USER'])
        return actual

    def isolation(self,dev,prod):
        for source,target in ((dev,prod),(prod,dev)):
            status,_,csrf=self.api(source,'/auth/csrf',cookie=source['cookie'],origin=source['origin'])
            require(status==200,'normal-csrf-bootstrap')
            csrf_headers={'X-CSRF-Token':json.loads(csrf)['csrf_token']}
            self.check(source['name']+'-cross-jwt-denied',self.api(target,'/users/me',token=source['token'])[0]==401)
            self.check(source['name']+'-cross-cookie-denied',self.api(target,'/auth/refresh',method='POST',cookie=source['cookie'],origin=target['origin'],headers=csrf_headers)[0]==401)
            self.check(source['name']+'-cross-origin-denied',self.api(target,'/auth/refresh',method='POST',cookie=target['cookie'],origin=source['origin'],headers=csrf_headers)[0]==403)
        self.check('distinct-secrets',all(dev['environment'][k]!=prod['environment'][k] for k in
                   ('POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD','JWT_SECRET_KEY','SMTP_PASSWORD','FRONTEND_ORIGINS')))
        devinfo=self.inspect(dev);prodinfo=self.inspect(prod)
        prod_db=next(c for c in prodinfo if c['Config']['Labels']['com.docker.compose.service']=='db')
        prodip=next(iter(prod_db['NetworkSettings']['Networks'].values()))['IPAddress']
        # First prove this exact target reachable internally, then deny from dev.
        probe='import socket,sys;s=socket.socket();s.settimeout(3);r=s.connect_ex((sys.argv[1],5432));s.close();sys.exit(0 if r==0 else 1)'
        require(self.compose(prod,'exec','-T','app','python','-c',probe,prodip).returncode==0,'prod-db-control-reachable')
        self.check('cross-network-denied',self.compose(dev,'exec','-T','app','python','-c',probe,prodip,okay=True).returncode!=0)
        # Independent credential denial on target's network (not conflated with TCP denial).
        script='import psycopg,sys\ntry:\n c=psycopg.connect(host="db",dbname=sys.argv[1],user=sys.argv[2],password=sys.argv[3],connect_timeout=3);c.close()\nexcept psycopg.OperationalError:sys.exit(7)\nelse:sys.exit(0)'
        wrong=self.compose(prod,'exec','-T','app','python','-c',script,prod['environment']['POSTGRES_DB'],
                           dev['environment']['POSTGRES_USER'],dev['environment']['POSTGRES_PASSWORD'],okay=True)
        self.check('cross-db-credentials-denied',wrong.returncode==7)
        baseline=self.fingerprint(prod);self.record['prod_baseline']=baseline
        require(self.api(dev,'/users/me',method='PATCH',token=dev['token'],value={'name':'Synthetic dev change'})[0]==200,'dev-write')
        self.preserved(prod,baseline,'prod-after-dev-write')
        self.compose(dev,'stop','proxy','app')
        self.compose(dev,'run','--rm','migrate','python','-m','alembic','-c','alembic.ini','downgrade','0002_accounts')
        self.up(dev);self.preserved(prod,baseline,'prod-after-dev-migration')
        self.compose(dev,'stop','proxy','app','migrate')
        self.sql(dev,"UPDATE alembic_version SET version_num='invalid_101'")
        failed=self.compose(dev,'up','-d','--force-recreate','migrate','app',okay=True,timeout=90)
        self.failed_gate(dev,'dev-migration-failure-blocks-startup',failed)
        self.preserved(prod,baseline,'prod-after-dev-migration-failure')
        self.cleanup_project(dev,volumes=True)
        self.up(dev);self.preserved(prod,baseline,'prod-after-dev-reset')
        self.compose(dev,'stop','proxy','app','migrate')
        original=dev['environment']['JWT_SECRET_KEY'];dev['environment']['JWT_SECRET_KEY']='invalid'
        self.save(dev)
        failed=self.compose(dev,'up','-d','--force-recreate','migrate','app',okay=True,timeout=90)
        self.failed_gate(dev,'dev-invalid-secret-blocks-startup',failed)
        self.preserved(prod,baseline,'prod-after-invalid-dev-secret')
        dev['environment']['JWT_SECRET_KEY']=secrets.token_hex(48)
        self.check('dev-secret-replaced',original!=dev['environment']['JWT_SECRET_KEY'])
        self.save(dev);self.up(dev);self.preserved(prod,baseline,'prod-after-dev-secret-replacement')
        self.journey(dev)
        self.compose(prod,'up','-d','--force-recreate','app','proxy',timeout=120)
        self.preserved(prod,baseline,'prod-after-recreate')
        self.cleanup_project(prod,volumes=False);self.up(prod)
        self.preserved(prod,baseline,'prod-after-down-up-retained-volumes')

    def browser(self,dev,prod):
        home=self.private/'browser-home';home.mkdir()
        nss=home/'.pki/nssdb';nss.mkdir(parents=True)
        self.run(['certutil','-N','-d','sql:'+str(nss),'--empty-password'])
        self.run(['certutil','-A','-d','sql:'+str(nss),'-n','Disposable101','-t','C,,','-i',str(self.private/'ca.pem')])
        config={'stacks':[{k:s[k] for k in ('name','origin','email','password')} for s in (dev,prod)],
                'output':str(self.private/'browser-result.json')}
        configfile=self.private/'browser.json';configfile.write_text(json.dumps(config))
        child=dict(self.env,HOME=str(home),REHEARSAL101_BROWSER_CONFIG=str(configfile))
        # Browser binary path remains explicit because HOME changes cache resolution.
        if 'PLAYWRIGHT_BROWSERS_PATH' in os.environ:child['PLAYWRIGHT_BROWSERS_PATH']=os.environ['PLAYWRIGHT_BROWSERS_PATH']
        bounded(['node',str(ROOT/'ops/rehearsal101/browser.cjs')],env=child,timeout=90)
        self.record['browser']=json.loads((self.private/'browser-result.json').read_text())
        self.check('browser-cookie-isolation',self.record['browser']['result']=='PASS')

    def validate_cleanup(self,stack):
        project=stack['project']
        for kind,args in [('container',['docker','ps','-aq']),('volume',['docker','volume','ls','-q']),('network',['docker','network','ls','-q'])]:
            names=self.run(args+['--filter','label=com.docker.compose.project='+project]).stdout.split()
            if not names:continue
            info=json.loads(self.run(['docker',kind,'inspect',*names]).stdout)
            for item in info:
                labels=item['Config']['Labels'] if kind=='container' else item['Labels']
                require(labels.get(LABEL)==self.owner and labels.get('com.docker.compose.project')==project,'cleanup-ownership')
                if kind!='container':require(item['Name'].startswith(project+'_'),'cleanup-name')

    def cleanup_project(self,stack,volumes):
        self.validate_cleanup(stack)
        self.compose(stack,'down',*(['--volumes'] if volumes else []),'--remove-orphans','--timeout','10',timeout=60)

    def provenance(self):
        self.record['source']=self.run(['git','rev-parse','HEAD']).stdout.strip()
        self.record['source_tree_clean']=not self.run(['git','status','--porcelain','--untracked-files=no']).stdout.strip()
        require(self.record['source_tree_clean'],'source-tree-dirty')
        self.record['run']={key:os.environ.get(key,'local') for key in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_REPOSITORY')}
        self.record['started_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        self.record['host']={'system':platform.platform(),'kernel':platform.release(),'architecture':platform.machine(),
                             'cpu_count':os.cpu_count(),'cpu_model':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown'),
                             'memory_kib':int(re.search(r'MemTotal:\s+(\d+)',Path('/proc/meminfo').read_text())[1]),
                             'free_disk_bytes':shutil.disk_usage(ROOT).free,
                             'docker':self.run(['docker','version','--format','{{.Server.Version}}']).stdout.strip(),
                             'compose':self.run(['docker','compose','version','--short']).stdout.strip()}
        self.record['input_sha256']={str(p.relative_to(ROOT)).replace('\\','/'):digest(p.read_bytes())
              for pattern in ('ops/rehearsal101/*','tools/rehearsal101*.py','.github/workflows/rehearsal101.yml')
              for p in ROOT.glob(pattern) if p.is_file()}
        self.record['input_sha256'].update({p:digest((ROOT/p).read_bytes()) for p in ('Dockerfile','compose.yaml','requirements.lock','e2e/smtp_sink.py')})
        self.record['caps_cpu_memory_mib']=CAPS
        self.record['cpu_normalization']='100 percent = one logical CPU; x64 vCPU is not Oracle ARM OCPU'
        self.record['declared_cpu_budget']=os.cpu_count()
        self.record['sampler_seconds']=5

    def images(self):
        self.record['images']={}
        pins=json.loads((ROOT/'ops/rehearsal101/images.json').read_text())
        for name,pin in pins.items():
            repository=pin.split(':',1)[0];expected=pin.split('@')[1]
            token=json.load(urllib.request.urlopen('https://auth.docker.io/token?service=registry.docker.io&scope=repository:'+repository+':pull',timeout=15))['token']
            req=urllib.request.Request('https://registry-1.docker.io/v2/'+repository+'/manifests/'+expected,
                headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'})
            with urllib.request.urlopen(req,timeout=15) as response:raw=response.read(1024*1024)
            require('sha256:'+digest(raw)==expected,'registry-index-digest')
            manifest=json.loads(raw)
            platforms={m['platform'].get('os','')+'/'+m['platform'].get('architecture',''):m['digest'] for m in manifest['manifests']}
            require(all(p in platforms for p in ('linux/amd64','linux/arm64')),'registry-multiarch')
            self.run(['docker','pull',pin],timeout=180)
            self.record['images'][name]={'pin':pin,'platforms':platforms,
                'actual':json.loads(self.run(['docker','image','inspect',pin]).stdout)[0]['Architecture']}
        self.pins=pins
        self.run(['docker','build','--label',LABEL+'='+self.owner,'-t',self.image,'.'],timeout=600)
        self.record['application_image_id']=self.run(['docker','image','inspect',self.image,'--format','{{.Id}}']).stdout.strip()

    def main(self):
        self.record['active_stage']='provenance';self.provenance()
        self.record['active_stage']='certificates';self.certificates()
        self.record['active_stage']='images';self.images()
        dev=self.stack('dev');prod=self.stack('prod')
        self.record['active_stage']='dev-startup';self.up(dev)
        self.record['active_stage']='prod-startup';self.up(prod)
        self.record['active_stage']='dev-normal-journey';self.journey(dev)
        self.record['active_stage']='prod-normal-journey';self.journey(prod)
        self.record['active_stage']='browser-isolation'
        self.browser(dev,prod)
        self.record['active_stage']='destructive-dev-isolation'
        self.isolation(dev,prod)
        self.record['active_stage']='capacity'
        from tools.rehearsal101_capacity import capacity
        capacity(self,dev,prod)
        self.record['result']='PASS'

    def cleanup(self):
        # Cleanup retains its own bounded allowance even after the main deadline.
        self.deadline=time.monotonic()+90
        okay=True
        for stack in reversed(self.projects):
            try:
                self.cleanup_project(stack,volumes=True)
                for command in (['docker','ps','-aq'],['docker','volume','ls','-q'],['docker','network','ls','-q']):
                    require(not self.run(command+['--filter','label=com.docker.compose.project='+stack['project']]).stdout.strip(),'cleanup-remains')
            except Exception:okay=False
        try:
            info=self.run(['docker','image','inspect',self.image],okay=True)
            if info.returncode==0:
                require(json.loads(info.stdout)[0]['Config']['Labels'].get(LABEL)==self.owner,'image-ownership')
                self.run(['docker','image','rm',self.image])
            self.record['owned_image_removed']=self.run(['docker','image','inspect',self.image],okay=True).returncode!=0
        except Exception:okay=False
        # Exact freshly-created directory only; refuse symlink/replaced location.
        try:
            require(self.private.name.startswith(self.owner+'-') and not self.private.is_symlink()
                    and self.private.resolve().parent==Path(tempfile.gettempdir()).resolve(),'private-cleanup-path')
            shutil.rmtree(self.private)
            self.record['private_files_removed']=not self.private.exists()
        except Exception:okay=False;self.record['private_files_removed']=False
        self.record['cleanup']=okay and self.record.get('owned_image_removed',False) and self.record['private_files_removed']
        if not self.record['cleanup']:self.record['result']='FAIL'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--confirm-disposable',required=True,choices=['issue-101-synthetic-only'])
    parser.parse_args()
    require(sys.platform=='linux','linux-required')
    safe=ROOT/'rehearsal101-safe'
    require(not safe.is_symlink() and (not safe.exists() or not any(safe.iterdir())),'safe-directory-not-empty')
    safe.mkdir(exist_ok=True)
    controller=Rehearsal()
    try:controller.main()
    except Failure as error:controller.record['failure_stage']=str(error)
    except Exception:controller.record['failure_stage']='unexpected-controller-error'
    finally:
        controller.cleanup()
        controller.record['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        (safe/'summary.json').write_text(json.dumps(controller.record,indent=2)+'\n')
    print(json.dumps({key:controller.record[key] for key in ('result','cleanup')}))
    return 0 if controller.record['result']=='PASS' else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Failure:print('Rehearsal invocation refused');sys.exit(1)
