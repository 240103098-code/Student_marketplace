"""Secret-free implemented-suite CI; native output stays in private memory/files."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from tools.e2e_stack import Failure, run

ROOT=Path(__file__).resolve().parents[1]
PG_IMAGE='postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8'
LABEL='marketplace.ci.owner'

def unittest_counts(output):
    match=re.search(r'^Ran (\d+) tests? in ',output,re.M)
    if not match:raise Failure('backend-result-missing')
    count=int(match[1]);skips=sum(int(n) for n in re.findall(r'skipped=(\d+)',output))
    failed=sum(int(n) for n in re.findall(r'failures=(\d+)',output));errors=sum(int(n) for n in re.findall(r'errors=(\d+)',output))
    finished=bool(re.search(r'^(?:OK|FAILED)(?:\s|$)',output,re.M))
    return {'discovered':count,'executed':count-skips,'skipped':skips,'failed':failed,'errors':errors,'passed':count-skips-failed-errors if finished else None}

def validate_counts(counts):
    if counts['discovered']<1 or counts['skipped'] or counts['passed']!=counts['discovered']:raise Failure('backend-tests')

def main():
    if len(sys.argv)!=1:raise Failure('unsupported-arguments')
    safe=ROOT/'ci-safe'
    safe.mkdir(exist_ok=True)
    if safe.is_symlink() or any(safe.iterdir()):raise Failure('safe-output-must-be-empty')
    for name in ('e2e-safe','compose-verification.json','compose-desktop.png','compose-mobile.png'):
        if (ROOT/name).exists():raise Failure('preserve-existing-output')
    owner='marketplace92-'+uuid.uuid4().hex[:20];image=owner+':local';container=owner+'-pg';volume=owner+'-pgdata'
    private=Path(tempfile.mkdtemp(prefix=owner+'-'));private.chmod(0o700)
    env={key:os.environ[key] for key in ('PATH','HOME','SYSTEMROOT','DOCKER_HOST','DOCKER_CONTEXT','DOCKER_CONFIG','XDG_RUNTIME_DIR') if key in os.environ}
    env.update(CI='true',PYTHONUNBUFFERED='1',POSTGRES_USER='marketplace_test',POSTGRES_PASSWORD=secrets.token_hex(32),POSTGRES_DB='student_marketplace_test_'+uuid.uuid4().hex[:16])
    record={'result':'FAIL','checks':[],'cleanup':False};stage='prerequisites'
    def checked(name):record['checks'].append(name)
    def execute(args,timeout=1800,**kwargs):return run(args,env,timeout=timeout,**kwargs)
    def owned(kind,identity):
        template='{{index .Config.Labels "'+LABEL+'"}}' if kind in ('container','image') else '{{index .Labels "'+LABEL+'"}}'
        prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
        result=execute(prefix+[identity,'--format',template],okay=True,timeout=20)
        if result.returncode:return False
        if result.stdout.strip()!=owner:raise Failure('cleanup-ownership')
        return True
    try:
        record['candidate']=execute(['git','rev-parse','HEAD']).stdout.strip()
        record['python']=sys.version.split()[0];record['node']=execute(['node','--version']).stdout.strip();record['npm']=execute(['npm','--version']).stdout.strip()
        if (record['python'],record['node'],record['npm'])!=('3.13.15','v24.19.0','12.2.0'):raise Failure('pinned-toolchain')
        record['docker']=execute(['docker','version','--format','{{.Server.Version}}']).stdout.strip();record['compose']=execute(['docker','compose','version','--short']).stdout.strip()
        tracked=execute(['git','ls-files']).stdout.splitlines();prefixes=('backend/','frontend/','tests/','tools/','migrations/','migrations_sqlite/','e2e/','.github/workflows/')
        paths=[p for p in tracked if p.startswith(prefixes) or p in ('Dockerfile','compose.yaml','openapi.yml','requirements.lock','requirements-dev.lock','pyproject.toml','alembic.ini','alembic-sqlite.ini')]
        record['input_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
        execute(['docker','volume','create','--label',LABEL+'='+owner,volume])
        execute(['docker','run','--detach','--name',container,'--label',LABEL+'='+owner,'--publish','127.0.0.1::5432','--mount','type=volume,source='+volume+',target=/var/lib/postgresql','--env','POSTGRES_USER','--env','POSTGRES_PASSWORD','--env','POSTGRES_DB',PG_IMAGE],timeout=180)
        deadline=time.monotonic()+60
        while True:
            if execute(['docker','exec',container,'pg_isready','-U',env['POSTGRES_USER'],'-d',env['POSTGRES_DB']],okay=True,timeout=5).returncode==0:break
            if time.monotonic()>deadline:raise Failure('postgres-startup')
            time.sleep(1)
        port=execute(['docker','port',container,'5432/tcp']).stdout.strip()
        if not re.fullmatch(r'127\.0\.0\.1:[0-9]+',port):raise Failure('database-not-loopback')
        env['TEST_DATABASE_URL']='postgresql+psycopg://'+env['POSTGRES_USER']+':'+env['POSTGRES_PASSWORD']+'@'+port+'/'+env['POSTGRES_DB'];env['TEST_DATABASE_CONFIRM']=env['POSTGRES_DB']
        record['postgresql']=execute(['docker','exec',container,'psql','-U',env['POSTGRES_USER'],'-d',env['POSTGRES_DB'],'-At','-c','SHOW server_version']).stdout.strip()
        checked('fresh-guarded-loopback-postgresql')
        stage='backend-tests';backend=execute([sys.executable,'-m','unittest','discover','-s','tests','-v'],okay=True,timeout=1200)
        native=backend.stdout+'\n'+backend.stderr
        record['backend']=unittest_counts(native)
        record['backend']['failed_test_ids']=[module+'.'+method for method,module in re.findall(r'^(?:FAIL|ERROR): ([A-Za-z0-9_]{1,128}) \(([A-Za-z0-9_.]{1,256})\)$',native,re.M)]
        validate_counts(record['backend'])
        if backend.returncode:raise Failure('backend-tests')
        checked(stage)
        stage='canonical-openapi';execute([sys.executable,'-m','tools.export_openapi','--check']);execute([sys.executable,'-m','tools.check_e2e_map']);checked(stage)
        stage='frontend-tests';frontend_report=private/'vitest.json'
        execute(['npm','ci','--prefix','frontend','--no-audit','--no-fund'],timeout=300)
        frontend_result=execute(['npm','run','test','--prefix','frontend','--','--run','--maxWorkers=2','--reporter=json','--outputFile='+str(frontend_report)],timeout=600,okay=True)
        report=json.loads(frontend_report.read_text());record['frontend']={key:report[key] for key in ('numTotalTests','numPassedTests','numFailedTests','numPendingTests','numTodoTests')}
        if frontend_result.returncode or record['frontend']['numTotalTests']<1 or record['frontend']['numPassedTests']!=record['frontend']['numTotalTests'] or any(record['frontend'][key] for key in ('numFailedTests','numPendingTests','numTodoTests')):raise Failure('frontend-counts')
        checked(stage)
        for label,command in [('frontend-typecheck',['npm','run','typecheck','--prefix','frontend']),('frontend-build',['npm','run','build','--prefix','frontend']),('frontend-production-mock-exclusion',['node','tools/check_frontend_build.mjs'])]:
            stage=label;execute(command,timeout=300);checked(stage)
        stage='single-image-build';execute(['docker','build','--label',LABEL+'='+owner,'--tag',image,'.'],timeout=900)
        image_id=execute(['docker','image','inspect',image,'--format','{{.Id}}']).stdout.strip();record['shared_image_id']=image_id;record['positive_chain_build_count']=1
        env.update(MARKETPLACE_TEST_IMAGE=image,MARKETPLACE_TEST_IMAGE_ID=image_id,MARKETPLACE_TEST_IMAGE_OWNER=owner,MARKETPLACE_TEST_PRIVATE_ROOT=str(private),GITHUB_SHA=record['candidate'],CONTAINER_PLAYWRIGHT_MODULE=str(ROOT/'e2e/node_modules/playwright'))
        browser=execute(['node','-e',"console.log(require('./e2e/node_modules/playwright').chromium.executablePath())"]).stdout.strip()
        if not Path(browser).is_file():raise Failure('matching-browser-missing')
        env['CONTAINER_BROWSER']=browser
        stage='compose-readiness-persistence';compose=execute([sys.executable,'-m','tools.compose_smoke'],okay=True,timeout=1200)
        source=ROOT/'compose-verification.json'
        if source.exists():
            value=json.loads(source.read_text());(safe/'compose.json').write_text(json.dumps(value,indent=2)+'\n')
        else:raise Failure('compose-record-missing')
        if compose.returncode or value['result']!='PASS' or value['application_image_id']!=image_id or value.get('borrowed_image_preserved') is not True:raise Failure('compose-verification')
        checked(stage)
        stage='playwright-real-compose';result=execute([sys.executable,'-m','tools.e2e_stack'],okay=True,timeout=600)
        e2e=ROOT/'e2e-safe'
        for name in ('run.json','tests.json','student-stages.json','admin-stages.json','student-masked.png','admin-masked.png'):
            if (e2e/name).is_file():shutil.copyfile(e2e/name,safe/('e2e-'+name))
        value=json.loads((e2e/'run.json').read_text())
        if result.returncode or value['result']!='PASS' or value['image_id']!=image_id or value.get('borrowed_image_preserved') is not True:raise Failure('playwright-verification')
        record['playwright_tests']=len(value['tests']['tests']);record['playwright']=value['playwright'];record['browser_revision']=value['browser_revision'];checked(stage)
        record['result']='PASS'
    except Failure as error:record['failure_stage']=stage;record['failure_kind']=str(error)
    except Exception:record['failure_stage']=stage;record['failure_kind']='controller-failure'
    finally:
        try:
            source=ROOT/'compose-verification.json'
            if source.is_file():
                value=json.loads(source.read_text())
                (safe/'compose.json').write_text(json.dumps(value,indent=2)+'\n')
            for name in ('run.json','tests.json','student-stages.json','admin-stages.json','student-masked.png','admin-masked.png'):
                source=ROOT/'e2e-safe'/name
                if source.is_file():shutil.copyfile(source,safe/('e2e-'+name))
        except Exception:record['diagnostic_copy_failed']=True
        outcomes=[]
        # Child timeouts may prevent their finally blocks. Their projects and private
        # roots are deterministically derived from our unguessable owned identity.
        suffix=owner.split('-')[1]
        for project in ('marketplace59-'+suffix[:12],'marketplace59-'+suffix[:12]+'-failure','marketplace60-'+suffix):
            try:
                for kind,listing in [('container',['docker','ps','-aq']),('network',['docker','network','ls','-q']),('volume',['docker','volume','ls','-q'])]:
                    resources=execute(listing+['--filter','label=com.docker.compose.project='+project],timeout=20).stdout.split()
                    for identity in resources:
                        prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
                        template='{{index .Config.Labels "com.docker.compose.project"}}' if kind in ('container','image') else '{{index .Labels "com.docker.compose.project"}}'
                        if execute(prefix+[identity,'--format',template],timeout=20).stdout.strip()!=project:raise Failure('child-cleanup-ownership')
                        remove=['docker','rm','--force',identity] if kind=='container' else ['docker',kind,'rm',identity]
                        execute(remove,timeout=30)
                    outcomes.append(not execute(listing+['--filter','label=com.docker.compose.project='+project],timeout=20).stdout.strip())
            except Exception:outcomes.append(False)
        record['owned_child_compose_resources_absent']=all(outcomes)
        for kind,identity in [('container',container),('volume',volume),('image',image)]:
            try:
                if owned(kind,identity):
                    command=['docker','rm','--force',identity] if kind=='container' else ['docker',kind,'rm',identity]
                    execute(command,timeout=45)
                prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
                outcomes.append(execute(prefix+[identity],okay=True,timeout=20).returncode!=0)
            except Exception:outcomes.append(False)
        record['owned_postgres_container_volume_and_shared_image_absent']=all(outcomes)
        # These fixed output paths were absent at entry and generated only by our children.
        for name in ('compose-verification.json','compose-desktop.png','compose-mobile.png'):
            try:(ROOT/name).unlink(missing_ok=True)
            except OSError:outcomes.append(False)
        for directory in (ROOT/'e2e-safe',private):
            try:
                if directory.exists() and not directory.is_symlink():shutil.rmtree(directory)
                outcomes.append(not directory.exists())
            except OSError:outcomes.append(False)
        record['cleanup']=all(outcomes)
        if not record['cleanup']:record['result']='FAIL'
        (safe/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({key:record[key] for key in ('result','checks','cleanup')}))
    return 0 if record['result']=='PASS' else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:print('Implemented-suite CI refused or failed; native details suppressed.');raise SystemExit(1)
