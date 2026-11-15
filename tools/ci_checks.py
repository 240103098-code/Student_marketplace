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

from tools.e2e_stack import Failure

ROOT=Path(__file__).resolve().parents[1]
PG_IMAGE='postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8'
LABEL='marketplace.ci.owner'

# Fixed public vocabulary. Never infer these labels from argv/output/environment.
OPERATIONS=frozenset({
    'source-revision','node-version','npm-version','docker-version','compose-version',
    'source-inventory','postgres-volume-create','postgres-container-start',
    'postgres-readiness','postgres-loopback-port','postgres-version','backend-suite',
    'openapi-check','e2e-map-check','frontend-install','frontend-suite',
    'frontend-typecheck','frontend-build','frontend-production-mock-exclusion',
    'application-image-build','application-image-identity','browser-executable',
    'compose-suite','playwright-suite','cleanup-owned-inspect','cleanup-child-list',
    'cleanup-child-inspect','cleanup-child-remove','cleanup-owned-remove',
    'cleanup-owned-absence',
})
FAILURE_CLASSES=frozenset({'exit-status','timeout','process-start','readiness-deadline','invalid-operation','invalid-result'})
STAGES=frozenset({'prerequisites','backend-tests','canonical-openapi','frontend-tests',
                  'frontend-typecheck','frontend-build','frontend-production-mock-exclusion',
                  'single-image-build','compose-readiness-persistence','playwright-real-compose'})
FAILURE_KINDS=frozenset({'pinned-toolchain','cleanup-ownership','postgres-startup',
    'database-not-loopback','backend-result-missing','backend-tests','frontend-counts',
    'matching-browser-missing','compose-record-missing','compose-verification',
    'playwright-verification','child-cleanup-ownership'})


class OperationFailure(Failure):
    def __init__(self, operation, classification, exit_status=None):
        approved=isinstance(operation,str) and operation in OPERATIONS
        self.operation=operation if approved else 'unapproved-operation'
        self.classification=classification if approved and isinstance(classification,str) and classification in FAILURE_CLASSES else 'invalid-operation'
        self.exit_status=exit_status if type(exit_status) is int and -2147483648<=exit_status<=2147483647 else None
        super().__init__('subprocess-operation')

    def public(self):
        result={'failure_operation':self.operation,'failure_class':self.classification,
                'failure_timeout':self.classification in ('timeout','readiness-deadline')}
        if self.exit_status is not None:result['failure_exit_status']=self.exit_status
        return result


def run_operation(operation=None,args=None,env=None,timeout=1800,input=None,okay=False):
    if not isinstance(operation,str) or operation not in OPERATIONS:
        raise OperationFailure(None,'invalid-operation')
    try:
        result=subprocess.run(args,cwd=ROOT,env=env,input=input,text=True,capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OperationFailure(operation,'timeout') from None
    except OSError:
        raise OperationFailure(operation,'process-start') from None
    if result.returncode and not okay:
        raise OperationFailure(operation,'exit-status',result.returncode)
    return result


def capture_failure(record,stage,error):
    # Called before cleanup; cleanup never replaces the first primary cause.
    if 'failure_kind' in record:return
    record['failure_stage']=stage if stage in STAGES else 'controller'
    if isinstance(error,OperationFailure):
        record['failure_kind']='subprocess-operation';record.update(error.public())
    else:
        value=str(error) if isinstance(error,Failure) else ''
        record['failure_kind']=value if value in FAILURE_KINDS else 'controller-failure'


def capture_cleanup_failure(record,error):
    value=error.public() if isinstance(error,OperationFailure) else {
        'failure_operation':'cleanup-controller','failure_class':'controller-error','failure_timeout':False}
    failures=record.setdefault('cleanup_failures',[])
    if len(failures)<32:failures.append(value)


def public_value(operation,value,pattern):
    value=value.strip()
    if not re.fullmatch(pattern,value):raise OperationFailure(operation,'invalid-result',0)
    return value


def await_postgres(execute,container,env,clock=time.monotonic,pause=time.sleep):
    deadline=clock()+60
    while True:
        result=execute('postgres-readiness',['docker','exec',container,'pg_isready','-U',env['POSTGRES_USER'],'-d',env['POSTGRES_DB']],okay=True,timeout=5)
        if result.returncode==0:return
        if clock()>deadline:raise OperationFailure('postgres-readiness','readiness-deadline',result.returncode)
        pause(1)

def unittest_counts(output):
    match=re.search(r'^Ran (\d+) tests? in ',output,re.M)
    if not match:raise Failure('backend-result-missing')
    count=int(match[1]);skips=sum(int(n) for n in re.findall(r'skipped=(\d+)',output))
    failed=sum(int(n) for n in re.findall(r'failures=(\d+)',output));errors=sum(int(n) for n in re.findall(r'errors=(\d+)',output))
    finished=bool(re.search(r'^(?:OK|FAILED)(?:\s|$)',output,re.M))
    return {'discovered':count,'executed':count-skips,'skipped':skips,'failed':failed,'errors':errors,'passed':count-skips-failed-errors if finished else None}

def validate_counts(counts):
    if counts['discovered']<1 or counts['skipped'] or counts['passed']!=counts['discovered']:raise Failure('backend-tests')

E2E_FILES=('run.json','tests.json','student-stages.json','admin-stages.json',
           'student-masked.png','admin-masked.png','registration-stages.json','registration-masked.png')
E2E_MODES=(('smoke','e2e-smoke-',(),False,{'student','admin'}),
           ('full','e2e-',('--selection','full'),False,{'student','admin','registration'}),
           ('registration','e2e-registration-only-',('--selection','registration'),False,{'registration'}),
           ('smoke','e2e-intentional-failure-',('--intentional-failure',),True,{'student','admin'}))


def playwright_modes(execute,safe,record,image_id):
    """Fixed real-stack runs share one owned image, never a database or limiter."""
    directory=ROOT/'e2e-safe'
    record['playwright_modes']=[]
    for selection,prefix,arguments,intentional,expected in E2E_MODES:
        if directory.exists():raise Failure('playwright-verification')
        try:
            result=execute('playwright-suite',[sys.executable,'-m','tools.e2e_stack',*arguments],okay=True,timeout=600)
            value=json.loads((directory/'run.json').read_text())
            if (result.returncode or value['result']!='PASS' or value['candidate']!=record['candidate']
                or value['image_id']!=image_id or value.get('borrowed_image_preserved') is not True
                or value.get('cleanup') is not True or value.get('private_files_removed') is not True
                or value.get('selection')!=selection or value.get('intentional_failure') is not intentional):
                raise Failure('playwright-verification')
            tests=value['tests'];rows=tests['tests'];ids=[row['test'] for row in rows]
            if intentional:
                # onBegin still validates the declared two-smoke topology. With
                # maxFailures=1, the unexecuted admin may have no onTestEnd row.
                if len(ids)!=len(set(ids)) or not set(ids)<=expected:raise Failure('playwright-verification')
                journey=json.loads((directory/'student-stages.json').read_text())
                if (value['playwright_exit']!=1 or tests['status']!='failed'
                    or not any(row=={'test':'student','status':'failed'} for row in rows)
                    or any(row!={'test':'admin','status':'skipped'} for row in rows if row['test']!='student')
                    or 'controlled-failure-check' not in journey['stages']
                    or not {'ui-register','private-smtp','ui-verify','ui-login','protected-reload','fresh-context-denied'}<=set(journey['completed'])):raise Failure('playwright-verification')
            elif len(ids)!=len(expected) or set(ids)!=expected or value['playwright_exit']!=0 or tests['status']!='passed' or any(row['status']!='passed' for row in rows):
                raise Failure('playwright-verification')
            record['playwright_modes'].append({'selection':selection,'intentional_failure':intentional,'result':'PASS','browser_status':tests['status'],'browser_exit':value['playwright_exit'],'tests':len(rows),'cleanup':True,'private_files_removed':True})
            if selection=='full':
                record['playwright_tests']=len(rows);record['playwright']=value['playwright'];record['browser_revision']=value['browser_revision']
        finally:
            # Preserve fixed safe evidence even when a child or its validation fails.
            if directory.is_symlink():raise Failure('playwright-verification')
            if directory.exists():
                for source in directory.iterdir():
                    if source.name not in E2E_FILES or source.is_symlink() or not source.is_file():raise Failure('playwright-verification')
                for name in E2E_FILES:
                    source=directory/name
                    if source.is_file():shutil.copyfile(source,safe/(prefix+name))
                # Exact fixed directory, verified file-only allowlist; never recursive deletion.
                for source in directory.iterdir():source.unlink()
                directory.rmdir()


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
    def execute(operation,args,timeout=1800,**kwargs):return run_operation(operation,args,env,timeout=timeout,**kwargs)
    def owned(kind,identity):
        template='{{index .Config.Labels "'+LABEL+'"}}' if kind in ('container','image') else '{{index .Labels "'+LABEL+'"}}'
        prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
        result=execute('cleanup-owned-inspect',prefix+[identity,'--format',template],okay=True,timeout=20)
        if result.returncode:return False
        if result.stdout.strip()!=owner:raise Failure('cleanup-ownership')
        return True
    try:
        record['candidate']=public_value('source-revision',execute('source-revision',['git','rev-parse','HEAD']).stdout,r'[a-f0-9]{40}')
        record['python']=sys.version.split()[0];record['node']=public_value('node-version',execute('node-version',['node','--version']).stdout,r'v[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}');record['npm']=public_value('npm-version',execute('npm-version',['npm','--version']).stdout,r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        if (record['python'],record['node'],record['npm'])!=('3.13.15','v24.19.0','12.2.0'):raise Failure('pinned-toolchain')
        record['docker']=public_value('docker-version',execute('docker-version',['docker','version','--format','{{.Server.Version}}']).stdout,r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}');record['compose']=public_value('compose-version',execute('compose-version',['docker','compose','version','--short']).stdout,r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        tracked=execute('source-inventory',['git','ls-files']).stdout.splitlines();prefixes=('backend/','frontend/','tests/','tools/','migrations/','migrations_sqlite/','e2e/','.github/workflows/')
        paths=[p for p in tracked if p.startswith(prefixes) or p in ('Dockerfile','compose.yaml','openapi.yml','requirements.lock','requirements-dev.lock','pyproject.toml','alembic.ini','alembic-sqlite.ini')]
        record['input_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
        execute('postgres-volume-create',['docker','volume','create','--label',LABEL+'='+owner,volume])
        execute('postgres-container-start',['docker','run','--detach','--name',container,'--label',LABEL+'='+owner,'--publish','127.0.0.1::5432','--mount','type=volume,source='+volume+',target=/var/lib/postgresql','--env','POSTGRES_USER','--env','POSTGRES_PASSWORD','--env','POSTGRES_DB',PG_IMAGE],timeout=180)
        await_postgres(execute,container,env)
        port=execute('postgres-loopback-port',['docker','port',container,'5432/tcp']).stdout.strip()
        if not re.fullmatch(r'127\.0\.0\.1:[0-9]+',port):raise Failure('database-not-loopback')
        env['TEST_DATABASE_URL']='postgresql+psycopg://'+env['POSTGRES_USER']+':'+env['POSTGRES_PASSWORD']+'@'+port+'/'+env['POSTGRES_DB'];env['TEST_DATABASE_CONFIRM']=env['POSTGRES_DB']
        version=execute('postgres-version',['docker','exec',container,'psql','-U',env['POSTGRES_USER'],'-d',env['POSTGRES_DB'],'-At','-c','SHOW server_version']).stdout
        record['postgresql']=public_value('postgres-version',version,r'[0-9]{1,3}\.[0-9]{1,3}(?: \(Debian [0-9]{1,3}\.[0-9]{1,3}-[0-9]{1,3}\.pgdg[0-9]{1,3}\+[0-9]{1,3}\))?')
        checked('fresh-guarded-loopback-postgresql')
        stage='backend-tests';backend=execute('backend-suite',[sys.executable,'-m','unittest','discover','-s','tests','-v'],okay=True,timeout=1200)
        native=backend.stdout+'\n'+backend.stderr
        record['backend']=unittest_counts(native)
        record['backend']['failed_test_ids']=[module+'.'+method for method,module in re.findall(r'^(?:FAIL|ERROR): ([A-Za-z0-9_]{1,128}) \(([A-Za-z0-9_.]{1,256})\)$',native,re.M)]
        validate_counts(record['backend'])
        if backend.returncode:raise Failure('backend-tests')
        checked(stage)
        stage='canonical-openapi';execute('openapi-check',[sys.executable,'-m','tools.export_openapi','--check']);execute('e2e-map-check',[sys.executable,'-m','tools.check_e2e_map']);checked(stage)
        stage='frontend-tests';frontend_report=private/'vitest.json'
        execute('frontend-install',['npm','ci','--prefix','frontend','--no-audit','--no-fund'],timeout=300)
        frontend_result=execute('frontend-suite',['npm','run','test','--prefix','frontend','--','--run','--maxWorkers=2','--reporter=json','--outputFile='+str(frontend_report)],timeout=600,okay=True)
        report=json.loads(frontend_report.read_text());record['frontend']={key:report[key] for key in ('numTotalTests','numPassedTests','numFailedTests','numPendingTests','numTodoTests')}
        if frontend_result.returncode or record['frontend']['numTotalTests']<1 or record['frontend']['numPassedTests']!=record['frontend']['numTotalTests'] or any(record['frontend'][key] for key in ('numFailedTests','numPendingTests','numTodoTests')):raise Failure('frontend-counts')
        checked(stage)
        for label,command in [('frontend-typecheck',['npm','run','typecheck','--prefix','frontend']),('frontend-build',['npm','run','build','--prefix','frontend']),('frontend-production-mock-exclusion',['node','tools/check_frontend_build.mjs'])]:
            stage=label;execute(label,command,timeout=300);checked(stage)
        stage='single-image-build';execute('application-image-build',['docker','build','--label',LABEL+'='+owner,'--tag',image,'.'],timeout=900)
        image_id=execute('application-image-identity',['docker','image','inspect',image,'--format','{{.Id}}']).stdout.strip();record['shared_image_id']=image_id;record['positive_chain_build_count']=1
        env.update(MARKETPLACE_TEST_IMAGE=image,MARKETPLACE_TEST_IMAGE_ID=image_id,MARKETPLACE_TEST_IMAGE_OWNER=owner,MARKETPLACE_TEST_PRIVATE_ROOT=str(private),GITHUB_SHA=record['candidate'],CONTAINER_PLAYWRIGHT_MODULE=str(ROOT/'e2e/node_modules/playwright'))
        browser=execute('browser-executable',['node','-e',"console.log(require('./e2e/node_modules/playwright').chromium.executablePath())"]).stdout.strip()
        if not Path(browser).is_file():raise Failure('matching-browser-missing')
        env['CONTAINER_BROWSER']=browser
        stage='compose-readiness-persistence';compose=execute('compose-suite',[sys.executable,'-m','tools.compose_smoke'],okay=True,timeout=1200)
        source=ROOT/'compose-verification.json'
        if source.exists():
            value=json.loads(source.read_text());(safe/'compose.json').write_text(json.dumps(value,indent=2)+'\n')
        else:raise Failure('compose-record-missing')
        if compose.returncode or value['result']!='PASS' or value['application_image_id']!=image_id or value.get('borrowed_image_preserved') is not True:raise Failure('compose-verification')
        checked(stage)
        stage='playwright-real-compose';playwright_modes(execute,safe,record,image_id);checked(stage)
        record['result']='PASS'
    except Exception as error:capture_failure(record,stage,error)
    finally:
        try:
            source=ROOT/'compose-verification.json'
            if source.is_file():
                value=json.loads(source.read_text())
                (safe/'compose.json').write_text(json.dumps(value,indent=2)+'\n')
        except Exception:record['diagnostic_copy_failed']=True
        outcomes=[]
        # Child timeouts may prevent their finally blocks. Their projects and private
        # roots are deterministically derived from our unguessable owned identity.
        suffix=owner.split('-')[1]
        for project in ('marketplace59-'+suffix[:12],'marketplace59-'+suffix[:12]+'-failure','marketplace60-'+suffix):
            try:
                for kind,listing in [('container',['docker','ps','-aq']),('network',['docker','network','ls','-q']),('volume',['docker','volume','ls','-q'])]:
                    resources=execute('cleanup-child-list',listing+['--filter','label=com.docker.compose.project='+project],timeout=20).stdout.split()
                    for identity in resources:
                        prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
                        template='{{index .Config.Labels "com.docker.compose.project"}}' if kind in ('container','image') else '{{index .Labels "com.docker.compose.project"}}'
                        if execute('cleanup-child-inspect',prefix+[identity,'--format',template],timeout=20).stdout.strip()!=project:raise Failure('child-cleanup-ownership')
                        remove=['docker','rm','--force',identity] if kind=='container' else ['docker',kind,'rm',identity]
                        execute('cleanup-child-remove',remove,timeout=30)
                    outcomes.append(not execute('cleanup-child-list',listing+['--filter','label=com.docker.compose.project='+project],timeout=20).stdout.strip())
            except Exception as error:outcomes.append(False);capture_cleanup_failure(record,error)
        record['owned_child_compose_resources_absent']=all(outcomes)
        for kind,identity in [('container',container),('volume',volume),('image',image)]:
            try:
                if owned(kind,identity):
                    command=['docker','rm','--force',identity] if kind=='container' else ['docker',kind,'rm',identity]
                    execute('cleanup-owned-remove',command,timeout=45)
                prefix=['docker','inspect'] if kind=='container' else ['docker',kind,'inspect']
                outcomes.append(execute('cleanup-owned-absence',prefix+[identity],okay=True,timeout=20).returncode!=0)
            except Exception as error:outcomes.append(False);capture_cleanup_failure(record,error)
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
