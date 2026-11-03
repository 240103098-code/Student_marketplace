"""Bounded owned #60 controller. All native subprocess output remains private."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

REPO = Path(__file__).resolve().parents[1]
SAFE = REPO/'e2e-safe'

class Failure(Exception): pass

def run(args, env=None, timeout=180, input=None, okay=False):
    try:
        result = subprocess.run(args, cwd=REPO, env=env, input=input, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired): raise Failure('bounded-subprocess') from None
    if result.returncode and not okay: raise Failure('subprocess-status')
    return result

def compose(env, private, project, *args, **kwargs):
    if not re.fullmatch(r'marketplace60-[a-f0-9]{20}', project): raise Failure('project-ownership')
    return run(['docker','compose','--env-file',os.devnull,'--project-name',project,'-f',str(REPO/'compose.yaml'),'-f',str(private/'override.yaml'),*args],env,**kwargs)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--intentional-failure',action='store_true'); parser.add_argument('action',nargs='?'); args=parser.parse_args()
    if args.action == 'admin':
        private=Path(os.environ['E2E_PRIVATE']); config=json.loads((private/'controller.json').read_text()); email=sys.stdin.read()
        if not re.fullmatch(r'e2e-[a-f0-9-]{36}@sdu\.edu\.kz',email): raise Failure('identity')
        compose(config['env'],private,config['project'],'exec','-T','app','python','-m','backend.admin','--email',email,timeout=25)
        return
    if args.action: raise Failure('unsupported-action')
    if any(key in os.environ for key in ('PW_TEST_WORKERS','PW_TEST_SHARD','PW_TEST_RETRIES')): raise Failure('unsupported-parallel-override')
    SAFE.mkdir(exist_ok=True)
    # Only fixed allowlisted generated files; refuse stale/symlink directories.
    if SAFE.is_symlink() or any(SAFE.iterdir()): raise Failure('safe-directory-must-be-empty')
    project='marketplace60-'+uuid.uuid4().hex[:20]
    private=Path(tempfile.mkdtemp(prefix=project+'-')); private.chmod(0o700)
    record={'result':'FAIL','mode':'actual-compose-playwright','intentional_failure':args.intentional_failure,'stages':[],'cleanup':False}
    env={key:os.environ[key] for key in ('PATH','HOME','SYSTEMROOT','DOCKER_HOST','DOCKER_CONTEXT','DOCKER_CONFIG','XDG_RUNTIME_DIR') if key in os.environ}
    with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    env.update(POSTGRES_DB='marketplace',POSTGRES_USER='marketplace',POSTGRES_PASSWORD=secrets.token_hex(32),JWT_SECRET_KEY=secrets.token_hex(48),FRONTEND_ORIGINS=json.dumps([origin]),APP_PORT=str(port),APP_ENV='test',REFRESH_COOKIE_SECURE='false',MARKETPLACE_IMAGE=project+':local',SMTP_HOST='smtp',SMTP_PORT='2525',SMTP_USERNAME='fixture',SMTP_PASSWORD=secrets.token_hex(32),SMTP_FROM_EMAIL='fixture@sdu.edu.kz',SMTP_SECURITY='starttls')
    env['DATABASE_URL']='postgresql+psycopg://marketplace:'+env['POSTGRES_PASSWORD']+'@db:5432/marketplace'
    (private/'mail').mkdir(); (private/'mail').chmod(0o700)
    (private/'smtp.json').write_text(json.dumps({'username':env['SMTP_USERNAME'],'password':env['SMTP_PASSWORD']}))
    (private/'controller.json').write_text(json.dumps({'env':env,'project':project}))
    try:
        record['candidate']=run(['git','rev-parse','HEAD']).stdout.strip()
        inputs=['compose.yaml','Dockerfile','e2e/package-lock.json','e2e/playwright.config.cjs','e2e/fixtures.cjs','e2e/smoke.spec.cjs','e2e/safe-reporter.cjs','e2e/smtp_sink.py','tools/e2e_stack.py']
        record['input_sha256']={p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in inputs}
        record['docker']=run(['docker','version','--format','{{.Server.Version}}'],env).stdout.strip()
        record['compose']=run(['docker','compose','version','--short'],env).stdout.strip()
        record['node']=run(['node','--version'],env).stdout.strip()
        record['npm']=run(['npm','--version'],env).stdout.strip()
        for name in ('ca','server'):
            command=['openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',str(private/(name+'.key')),'-out',str(private/(name+'.csr')),'-subj','/CN='+('smtp' if name=='server' else 'marketplace60 fixture CA')]
            run(command,env)
        run(['openssl','x509','-req','-in',str(private/'ca.csr'),'-signkey',str(private/'ca.key'),'-days','1','-out',str(private/'ca.pem'),'-extfile',str(REPO/'e2e/ca.ext')],env)
        run(['openssl','x509','-req','-in',str(private/'server.csr'),'-CA',str(private/'ca.pem'),'-CAkey',str(private/'ca.key'),'-CAcreateserial','-days','1','-out',str(private/'server.pem'),'-extfile',str(REPO/'e2e/server.ext')],env)
        # App receives only the CA certificate; SMTP keys/inbox are never mounted in it.
        (private/'ca.pem').chmod(0o644)
        override={'services':{'smtp':{'image':env['MARKETPLACE_IMAGE'],'pull_policy':'never','user':'0:0','command':['python','/fixture/smtp_sink.py'],'volumes':[str(private)+':/fixture',str(REPO/'e2e/smtp_sink.py')+':/fixture/smtp_sink.py:ro'],'restart':'no','networks':['mail']},'app':{'environment':['SSL_CERT_FILE=/fixture-ca.pem'],'volumes':[str(private/'ca.pem')+':/fixture-ca.pem:ro'],'networks':['default','mail'],'depends_on':{'smtp':{'condition':'service_started'}}}},'networks':{'mail':{'internal':True}}}
        (private/'override.yaml').write_text(json.dumps(override))
        compose(env,private,project,'config','--quiet'); compose(env,private,project,'build','app',timeout=600)
        record['image_id']=run(['docker','image','inspect',env['MARKETPLACE_IMAGE'],'--format','{{.Id}}'],env).stdout.strip()
        compose(env,private,project,'up','--detach','--wait','--wait-timeout','150',timeout=180)
        record['stages'].append('owned-stack-started')
        with urllib.request.urlopen(origin+'/health/ready',timeout=8) as response:
            if response.status!=200: raise Failure('readiness')
        record['postgresql']=compose(env,private,project,'exec','-T','db','psql','-U','marketplace','-d','marketplace','-At','-c','SHOW server_version').stdout.strip()
        record['playwright']=json.loads((REPO/'e2e/node_modules/@playwright/test/package.json').read_text())['version']
        record['browser_revision']=[b for b in json.loads((REPO/'e2e/node_modules/playwright-core/browsers.json').read_text())['browsers'] if b['name'] in ('chromium','chromium-headless-shell')]
        child=dict(env,E2E_ORIGIN=origin,E2E_MAIL=str(private/'mail'),E2E_PRIVATE=str(private),E2E_PRIVATE_OUTPUT=str(private/'native-output'),E2E_SAFE_REPORT=str(SAFE/'tests.json'),E2E_SAFE_DIR=str(SAFE),E2E_PYTHON=sys.executable,E2E_INTENTIONAL_FAILURE='1' if args.intentional_failure else '0')
        result=run(['node',str(REPO/'e2e/node_modules/@playwright/test/cli.js'),'test','--config',str(REPO/'e2e/playwright.config.cjs')],child,timeout=210,okay=True)
        record['playwright_exit']=result.returncode
        tests=json.loads((SAFE/'tests.json').read_text()); record['tests']=tests
        if args.intentional_failure:
            if result.returncode==0 or tests['status']!='failed' or not any(t['test']=='student' and t['status']=='failed' for t in tests['tests']): raise Failure('intentional-failure-not-recognized')
            stages=json.loads((SAFE/'student-stages.json').read_text())
            if 'controlled-failure-check' not in stages['stages']: raise Failure('failure-before-journey')
        elif result.returncode or tests['status']!='passed' or len(tests['tests'])!=2: raise Failure('browser-journey')
        record['result']='PASS'
    except Failure as error: record['failure_stage']=str(error)
    except Exception: record['failure_stage']='controller-failure'
    finally:
        # Validate labels on every selected resource before project-scoped deletion.
        try:
            ids=run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project],env).stdout.split()
            for identity in ids:
                actual=run(['docker','inspect',identity,'--format','{{index .Config.Labels "com.docker.compose.project"}}'],env).stdout.strip()
                if actual!=project: raise Failure('cleanup-ownership')
            for kind in ('volume','network'):
                names=run(['docker',kind,'ls','-q','--filter','label=com.docker.compose.project='+project],env).stdout.split()
                for name in names:
                    actual=run(['docker',kind,'inspect',name,'--format','{{index .Labels "com.docker.compose.project"}}'],env).stdout.strip()
                    owned_name=run(['docker',kind,'inspect',name,'--format','{{.Name}}'],env).stdout.strip()
                    if actual!=project or not owned_name.startswith(project+'_'): raise Failure('cleanup-ownership')
            compose(env,private,project,'down','--volumes','--remove-orphans','--timeout','15',timeout=75)
            absent=[]
            for command in (['docker','ps','-aq'],['docker','volume','ls','-q'],['docker','network','ls','-q']):
                absent.append(not run(command+['--filter','label=com.docker.compose.project='+project],env).stdout.strip())
            run(['docker','image','rm',env['MARKETPLACE_IMAGE']],env,okay=True)
            record['owned_image_absent']=run(['docker','image','inspect',env['MARKETPLACE_IMAGE']],env,okay=True).returncode!=0
            record['cleanup']=all(absent) and record['owned_image_absent']
        except Exception: record['cleanup']=False
        try:
            shutil.rmtree(private)
            record['private_files_removed']=not private.exists()
        except OSError:
            record['private_files_removed']=False
        if not record['cleanup'] or not record['private_files_removed']:record['result']='FAIL'
        (SAFE/'run.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'result':record['result'],'intentional_failure':args.intentional_failure,'cleanup':record['cleanup']}))
    if record['result']!='PASS': raise SystemExit(1)

if __name__=='__main__':
    try: main()
    except Exception: print('E2E controller refused or could not complete invocation; native details suppressed'); raise SystemExit(1)
